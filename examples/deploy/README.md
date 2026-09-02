Production deployment configurations for the huey consumer: systemd,
supervisord, Docker and Docker Compose.

These files are included verbatim in the documentation. See the
"Deploying to Production" document at https://huey.readthedocs.io/ for
the full discussion of each, including Kubernetes and PaaS notes and a
production checklist.

The one thing to get right: huey shuts down gracefully on `SIGINT` and
treats `SIGTERM` as "stop immediately, interrupting running tasks", while
nearly every process supervisor defaults to stopping processes with
`SIGTERM`. Each config here sets the stop signal to `INT` accordingly.
Alternatively, run the consumer with `-g TERM` to make `SIGTERM` the
graceful signal and skip the stop-signal configuration.

Each config also passes `-t 55` (`--shutdown-timeout`) with a 60 second
supervisor deadline, so tasks that cannot finish in time are interrupted
by huey, emitting `SIGNAL_INTERRUPTED`, rather than lost to `SIGKILL`.
