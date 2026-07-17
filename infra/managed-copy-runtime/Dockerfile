FROM python:3.12-alpine@sha256:dbb1970cc04ce7d381c65efe8309c0c03d463e5b35c88f14d721796ad24cfbfd

LABEL francis.runtime.contract="stage18_managed_copy_runtime_v1"
LABEL francis.runtime.program_sha256="aa0802b54f102f70ac21e3388a9c48837ed68f5d1ec5aa15d76403f3af1c4b2a"

COPY --chown=65532:65532 src/francis/managed_copy_runtime.py /opt/francis/managed_copy_runtime.py

USER 65532:65532
ENTRYPOINT ["python", "/opt/francis/managed_copy_runtime.py"]
