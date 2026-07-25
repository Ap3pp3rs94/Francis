FROM python:3.12-alpine@sha256:dbb1970cc04ce7d381c65efe8309c0c03d463e5b35c88f14d721796ad24cfbfd

LABEL francis.runtime.contract="stage18_managed_copy_runtime_v1"
LABEL francis.runtime.program_sha256="834e94c90acca37716bd951aef5a10362c734804d4c56116bdce739338440fc0"

COPY --chown=65532:65532 src/francis/managed_copy_runtime.py /opt/francis/managed_copy_runtime.py

USER 65532:65532
ENTRYPOINT ["python", "/opt/francis/managed_copy_runtime.py"]
