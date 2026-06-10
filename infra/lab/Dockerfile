# Francis Lab v0 sandbox base image.
#
# Purpose: a minimal, auditable, Francis-owned base for the Lab sandbox runner.
# It contains NO application code, NO credentials, and NO external dependencies
# beyond the pinned public base. It provides only a POSIX shell + coreutils
# (BusyBox, via Alpine) so the Lab runtime can copy the read-only source into the
# writable tmpfs scratch and run detected commands.
#
# Isolation is enforced by the Lab runtime at run time (see
# `src/francis/ingest/lab/lab_runtime.py::build_run_argv`), not by this image:
# `--network none`, `--read-only` root, `--cap-drop ALL`,
# `--security-opt no-new-privileges`, pids/memory/cpu limits, read-only `/src`
# mount, and a size-limited tmpfs `/work`.
#
# Build (tag must match the Lab runtime default `FRANCIS_LAB_IMAGE`):
#   docker build -t francis-lab-base:pinned infra/lab
#
# Pinned base: Alpine 3.20 (minimal ~7MB official image), pinned by digest for
# supply-chain integrity. Verified locally: docker inspect alpine:3.20.
FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc

# Working directory matches the Lab runtime's tmpfs scratch mount (`-w /work`).
WORKDIR /work

# No ENTRYPOINT/CMD: the Lab runtime always supplies `/bin/sh -lc <script>`
# explicitly, so the image stays a passive, inspectable sandbox shell.
