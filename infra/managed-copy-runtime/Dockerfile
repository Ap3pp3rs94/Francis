FROM python:3.12-alpine@sha256:dbb1970cc04ce7d381c65efe8309c0c03d463e5b35c88f14d721796ad24cfbfd

LABEL francis.runtime.contract="stage18_managed_copy_runtime_v1"
LABEL francis.runtime.program_sha256="5c6ff6a28b6dee77d80980cbcf9bf0f30c6aea55bdc597178e2f7b07079e84ba"

COPY --chown=65532:65532 src/francis/managed_copy_runtime.py /opt/francis/managed_copy_runtime.py

USER 65532:65532
ENTRYPOINT ["python", "/opt/francis/managed_copy_runtime.py"]
