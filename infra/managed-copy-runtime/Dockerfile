FROM python:3.12-alpine@sha256:dbb1970cc04ce7d381c65efe8309c0c03d463e5b35c88f14d721796ad24cfbfd

LABEL francis.runtime.contract="stage18_managed_copy_runtime_v1"
LABEL francis.runtime.program_sha256="568b3e0cf395c3993fac6e3c088d1547317d7243eff60c98ed34fd8a9c1ec6cf"

COPY --chown=65532:65532 src/francis/managed_copy_runtime.py /opt/francis/managed_copy_runtime.py

USER 65532:65532
ENTRYPOINT ["python", "/opt/francis/managed_copy_runtime.py"]
