# scripts

Scripts that run on the home lab's hosts, outside Kubernetes. The cluster's
own host scripts (`cluster-power.sh`, `ci-runner.sh`, the router scripts) are
in the infrastructure repo's `scripts/` folder.

| Script | Does |
|---|---|
| [`disk-cleanup/`](disk-cleanup/README.md) | weekly cleanup of ubuntu-server's root disk (CI runner checkouts, Docker build cache, old journal), and the first fix for the disk alert |

Work happens on the `dev` branch, through a pull request to `main`.
