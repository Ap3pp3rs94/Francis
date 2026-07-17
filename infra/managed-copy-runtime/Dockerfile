FROM python:3.12-alpine@sha256:dbb1970cc04ce7d381c65efe8309c0c03d463e5b35c88f14d721796ad24cfbfd

COPY --chown=65532:65532 src/francis/managed_copy_runtime.py /opt/francis/managed_copy_runtime.py

USER 65532:65532
ENTRYPOINT ["python", "/opt/francis/managed_copy_runtime.py"]
