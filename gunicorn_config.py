# gunicorn config for CAPA-web
bind = "0.0.0.0:8050"
workers = 1              # single worker avoids cross-worker serverside-cache issues
threads = 8              # handle ~10 concurrent users via threads
timeout = 120            # RBF correction can take a few seconds
worker_class = "gthread"