"""
Color correction — port/redesign of MATLAB colorCorrectFun.

Design goals (bleaching-measurement context):
  * Output in LINEAR RGB (matches the endpoint measurement space).
  * Maximize reproducibility & accuracy in the coral tonal range
    (browns/greens -> bone white); the bright, near-neutral end matters most.
  * No white-clip hack: corals are masked downstream, so we only clip at the
    true gamut boundary and avoid distorting bright near-bleached pixels.

Algorithms:
  * Cross-Linear   (implemented) : linear model, fit linear-RGB -> linear-RGB
  * Cross-Quadrat  (todo)        : + squared terms
  * RBF            (todo)        : interpolation in LAB (production algorithm)
"""

import numpy as np
from skimage.color import lab2rgb, rgb2lab
from skimage import color as skcolor
from scipy.optimize import minimize
from scipy.spatial.distance import cdist

# Empirically measured LAB reference colors:
EMPIRICAL_LAB = np.array([
    [93.26, -1.09,  2.19], [71.11, -1.50,  3.56], [59.29, -3.51,  3.12],
    [44.50, -3.60,  3.87], [33.68, -1.92,  0.13], [22.10,  0.23, -1.45],
    [50.35, 44.74, 27.41], [87.58, -8.09, 86.45], [65.91,-39.72, 42.11],
    [65.90,-27.63,-30.40], [24.25, -0.61,-12.06], [48.96, 56.03, -7.27],
    [91.15, -0.01,  1.17], [45.59, 32.26, 23.27], [88.21, -1.12, 14.57],
    [36.18, 13.95, 11.26], [87.46, -7.22, 55.86], [61.89, -0.39, 46.53],
])

# Assigned LAB reference colors (for print only):
THEORETICAL_LAB = np.array([
    [100,   0,   0], [ 80,   0,   0], [ 60,   0,   0],
    [ 40,   0,   0], [ 20,   0,   0], [  0,   0,   0],
    [ 52,  74,  54], [ 95,  -6,  95], [ 69, -43,  50],
    [62,  -44, -50], [ 11,  10, -39], [ 52,  81,  -7],
    [95.2,   2.6,   -1.85], [37.46,   49.92,   43.64], [90.87,   1.52,   13.09],
    [30,   24.42,   37.95], [88.48,   -9.42,   52.94], [56.43,   -2.11,   59.4],
])

MIN_SWATCHES = 6


# ---------------------------------------------------------------------------
# Reference-color helpers (for UI + fitting targets)
# ---------------------------------------------------------------------------
def reference_rgb_swatches():
    """Return the 18 reference colors as 0-255 sRGB tuples for UI buttons."""
    rgb = lab2rgb(EMPIRICAL_LAB.reshape(1, -1, 3)).reshape(-1, 3)
    rgb = np.clip(rgb, 0, 1)
    return [tuple(int(round(c * 255)) for c in row) for row in rgb]


def reference_linear_rgb():
    """Reference colors as LINEAR-RGB, shape (18, 3), clipped to [0,1]."""
    srgb = lab2rgb(EMPIRICAL_LAB.reshape(1, -1, 3)).reshape(-1, 3)
    srgb = np.clip(srgb, 0, 1)
    return _srgb_to_linear(srgb)


# ---------------------------------------------------------------------------
# sRGB <-> linear-RGB (skimage-consistent conventions, floats in [0,1])
# ---------------------------------------------------------------------------
def _srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """sRGB (0..1) -> linear RGB (0..1). Standard sRGB EOTF."""
    srgb = np.asarray(srgb, dtype=np.float64)
    a = 0.055
    return np.where(srgb <= 0.04045,
                    srgb / 12.92,
                    ((srgb + a) / (1 + a)) ** 2.4)


def _linear_to_srgb(lin: np.ndarray) -> np.ndarray:
    """linear RGB (0..1) -> sRGB (0..1). Standard sRGB OETF."""
    lin = np.asarray(lin, dtype=np.float64)
    a = 0.055
    return np.where(lin <= 0.0031308,
                    lin * 12.92,
                    (1 + a) * np.power(np.clip(lin, 0, None), 1 / 2.4) - a)


def _decode_uint8_to_linear(img_u8: np.ndarray) -> np.ndarray:
    """uint8 sRGB image -> float64 linear-RGB image in [0,1]."""
    return _srgb_to_linear(img_u8.astype(np.float64) / 255.0)


def _encode_linear_to_uint8(lin: np.ndarray) -> np.ndarray:
    """float linear-RGB image -> uint8 sRGB image (clipped at gamut boundary)."""
    srgb = _linear_to_srgb(np.clip(lin, 0.0, 1.0))
    return np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)

# LAB normalization ranges:
_L_MIN, _L_MAX = 0.0, 100.0
_A_MIN, _A_MAX = -128.0, 127.0
_B_MIN, _B_MAX = -128.0, 127.0

def _normalize_lab(lab: np.ndarray) -> np.ndarray:
    out = np.empty_like(lab, dtype=np.float64)
    out[..., 0] = (lab[..., 0] - _L_MIN) / (_L_MAX - _L_MIN)
    out[..., 1] = (lab[..., 1] - _A_MIN) / (_A_MAX - _A_MIN)
    out[..., 2] = (lab[..., 2] - _B_MIN) / (_B_MAX - _B_MIN)
    return out


def _denormalize_lab(labn: np.ndarray) -> np.ndarray:
    out = np.empty_like(labn, dtype=np.float64)
    out[..., 0] = labn[..., 0] * (_L_MAX - _L_MIN) + _L_MIN
    out[..., 1] = labn[..., 1] * (_A_MAX - _A_MIN) + _A_MIN
    out[..., 2] = labn[..., 2] * (_B_MAX - _B_MIN) + _B_MIN
    return out


# ---------------------------------------------------------------------------
# Swatch sampling
# ---------------------------------------------------------------------------
def sample_swatches(img_u8: np.ndarray, rectangles: list):
    """
    For each SET swatch rectangle, compute the MEAN color in LINEAR RGB over
    the rectangle region.

    Returns
    -------
    measured_linear : (N, 3) float   mean linear-RGB of each marked swatch
    target_linear   : (N, 3) float   corresponding reference linear-RGB
    used_indices    : (N,) int       which reference-color indices were used
    """
    lin = _decode_uint8_to_linear(img_u8)
    ref_lin = reference_linear_rgb()
    H, W = lin.shape[:2]

    measured, target, used = [], [], []
    for r in rectangles:
        if not getattr(r, "is_set", False):
            continue
        x0 = int(max(0, np.floor(r.x)))
        y0 = int(max(0, np.floor(r.y)))
        x1 = int(min(W, np.ceil(r.x + r.w)))
        y1 = int(min(H, np.ceil(r.y + r.h)))
        if x1 <= x0 or y1 <= y0:
            continue
        patch = lin[y0:y1, x0:x1, :].reshape(-1, 3)
        measured.append(patch.mean(axis=0))
        target.append(ref_lin[r.index])
        used.append(r.index)

    if not measured:
        return (np.empty((0, 3)), np.empty((0, 3)), np.empty((0,), dtype=int))
    return (np.vstack(measured), np.vstack(target),
            np.asarray(used, dtype=int))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
class CorrectionError(Exception):
    """Raised when correction cannot be performed (e.g., too few swatches)."""


def color_correct(img_u8: np.ndarray, algorithm: str, rectangles: list) -> np.ndarray:
    """
    Apply color correction. Returns a uint8 sRGB image for display.
    The MEASUREMENT (linear-RGB) is recoverable from the returned image via
    _decode_uint8_to_linear, but for coral stats we'll correct+sample within
    the coral mask later, in linear space.

    Raises CorrectionError if inputs are insufficient.
    """
    if algorithm == "None":
        return img_u8

    measured, target, used = sample_swatches(img_u8, rectangles)
    if measured.shape[0] < MIN_SWATCHES:
        raise CorrectionError(
            f"Need at least {MIN_SWATCHES} marked swatches to color-correct "
            f"(have {measured.shape[0]})."
        )

    if algorithm == "Cross-Linear":
        return _apply_cross_linear(img_u8, measured, target)
    if algorithm == "Cross-Quadrat":
        raise CorrectionError("Cross-Quadrat not implemented yet.")
    if algorithm == "RBF Interpolation":
        return _apply_rbf(img_u8, measured, target)
    raise CorrectionError(f"Unknown algorithm: {algorithm}")


# ---------------------------------------------------------------------------
# Cross-Linear:  fit  target_linear = M @ [measured_linear; 1]  per channel
# ---------------------------------------------------------------------------
def _fit_linear_map(measured: np.ndarray, target: np.ndarray) -> np.ndarray:
    """
    Least-squares fit of an affine map (3x4) taking measured linear-RGB
    (with bias term) to target linear-RGB.

        target[:,k] = A[k,0]*r + A[k,1]*g + A[k,2]*b + A[k,3]
    """
    N = measured.shape[0]
    X = np.hstack([measured, np.ones((N, 1))])          # (N, 4)
    # Solve for each output channel; A is (4, 3), we store transposed as (3,4)
    coeffs, *_ = np.linalg.lstsq(X, target, rcond=None)  # (4, 3)
    return coeffs.T                                       # (3, 4)


def _apply_cross_linear(img_u8, measured, target) -> np.ndarray:
    A = _fit_linear_map(measured, target)               # (3, 4)
    lin = _decode_uint8_to_linear(img_u8)               # (H, W, 3)
    H, W, _ = lin.shape
    flat = lin.reshape(-1, 3)
    aug = np.hstack([flat, np.ones((flat.shape[0], 1))])  # (HW, 4)
    corrected = aug @ A.T                                 # (HW, 3)
    corrected = corrected.reshape(H, W, 3)
    return _encode_linear_to_uint8(corrected)

# ---------------------------------------------------------------------------
# RBF interpolation:  fit  in LAB space
# ---------------------------------------------------------------------------

def _rbf_kernel(D: np.ndarray, params) -> np.ndarray:
    """Gaussian x exponential kernel: exp(-(e1*D)^2) * exp(-e2*D).
    Matches the MATLAB rbf_kernel = @(D,b) exp(-(b(1)*D).^2).*exp(-b(2)*D)."""
    e1, e2 = params
    return np.exp(-((e1 * D) ** 2)) * np.exp(-e2 * D)


def _rbf_loo_error(params, Xn: np.ndarray, ref_n: np.ndarray) -> float:
    """
    Leave-one-out cross-validation error for given kernel params.
    Port of MATLAB EstimateEpsilon: for each swatch, fit on the rest,
    predict the held-out swatch, sum squared error over all channels.
    """
    n = Xn.shape[0]
    total = 0.0
    for s in range(n):
        keep = np.ones(n, dtype=bool)
        keep[s] = False
        Xtemp = Xn[keep]
        reftemp = ref_n[keep]

        Dtemp = cdist(Xtemp, Xtemp, metric="euclidean")
        phitemp = _rbf_kernel(Dtemp, params)
        w, *_ = np.linalg.lstsq(phitemp, reftemp, rcond=None)

        d_test = cdist(Xn[s:s + 1], Xtemp, metric="euclidean")
        phi_test = _rbf_kernel(d_test, params)
        pred = phi_test @ w                      # (1, 3)
        err = pred - ref_n[s:s + 1]              # (1, 3)
        total += float(np.sum(err ** 2))
    return total


def _apply_rbf(img_u8, measured_lin, target_lin) -> np.ndarray:
    """
    RBF interpolation color correction, performed in normalized LAB space.

    measured_lin, target_lin : (N,3) linear-RGB swatch means / references
    (we convert them to LAB here to fit in LAB, matching the MATLAB design).
    """
    # Convert swatch measured + reference from linear-RGB -> LAB.
    # skimage rgb2lab expects sRGB by default; we have LINEAR rgb, so tell it.
    Xlab = rgb2lab(measured_lin.reshape(1, -1, 3),
                   illuminant="D65").reshape(-1, 3)
    reflab = rgb2lab(target_lin.reshape(1, -1, 3),
                     illuminant="D65").reshape(-1, 3)

    Xn = _normalize_lab(Xlab)
    ref_n = _normalize_lab(reflab)

    # Optimize kernel params (e1, e2) via LOO CV, same init as MATLAB [1, 0.01].
    res = minimize(_rbf_loo_error, x0=np.array([1.0, 0.01]),
                   args=(Xn, ref_n), method="Nelder-Mead")
    best = res.x

    # Solve RBF weights on all swatches:
    D = cdist(Xn, Xn, metric="euclidean")
    phi = _rbf_kernel(D, best)
    weights, *_ = np.linalg.lstsq(phi, ref_n, rcond=None)   # (N, 3)

    # Interpolate every pixel:
    lin = _decode_uint8_to_linear(img_u8)                   # (H,W,3) linear rgb
    H, W, _ = lin.shape
    pix_lab = rgb2lab(lin, illuminant="D65").reshape(-1, 3)  # linear->LAB
    pix_n = _normalize_lab(pix_lab)

    Dpix = cdist(pix_n, Xn, metric="euclidean")             # (HW, N)
    phipix = _rbf_kernel(Dpix, best)                        # (HW, N)
    corrected_n = phipix @ weights                          # (HW, 3)

    corrected_lab = _denormalize_lab(corrected_n).reshape(H, W, 3)
    corrected_rgb = lab2rgb(corrected_lab, illuminant="D65")
    corrected_rgb = np.clip(corrected_rgb, 0.0, 1.0)
    return _encode_linear_to_uint8(corrected_rgb)