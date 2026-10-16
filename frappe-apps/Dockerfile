# Overlay: adds the custom `vidi_integration` app on top of the built LMS image.
# Fast rebuild (only the last 2 layers re-run).
#   build context = ./frappe-apps
ARG BASE_IMAGE=vidi-lms:latest
FROM ${BASE_IMAGE}

# The Frappe image runs as the `frappe` user; its virtualenv is env/.
COPY --chown=frappe:frappe vidi_integration /home/frappe/frappe-bench/apps/vidi_integration

RUN cd /home/frappe/frappe-bench && \
    env/bin/pip install --no-cache-dir -e apps/vidi_integration
