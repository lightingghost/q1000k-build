# Q1000K builder

This project automates builds of the OpenWrt initramfs and sysupgrade images
for the Quantum Fiber Q1000K.

The workflows build the `quantum_q1000k` device from
[`lightingghost/openwrt-q1000k`](https://github.com/lightingghost/openwrt-q1000k)
on its `main` branch. Each release contains exactly these artifacts:

- `*-quantum_q1000k-initramfs-recovery.itb`
- `*-quantum_q1000k-squashfs-sysupgrade.itb`

The source branch must define both Q1000K images before a workflow is run.
The Q1000K profile includes `luci-ssl`, with LuCI, the uHTTPd web server and
its RPC dependencies, for browser administration over HTTP or HTTPS.
The first firmware run falls back to the generic fastbuild bootstrap image and
then publishes this repository's cache and incremental image. The toolchain
and base-image workflows can be dispatched ahead of it to prime those caches.
All workflows replace any container-local output directories with the mounted
cache directories, so bootstrap builds publish their firmware artifacts.
The release step deliberately fails if either expected artifact is missing,
instead of publishing an incomplete firmware release.

Release tags include the 12-character OpenWrt source revision, so they remain
traceable even when the optional `profiles.json` image overview is disabled.

## Automatic source builds

`openwrt-q1000k` dispatches every push to `main` to the `fastbuild Q1000K`
workflow, which builds the commit SHA from that push. Manual runs remain
available through `workflow_dispatch` and build the latest `main` revision.

Create a fine-grained token restricted to `lightingghost/q1000k-build` with
**Contents: write**, then save it in `lightingghost/openwrt-q1000k` as the
`Q1000K_BUILD_DISPATCH_TOKEN` Actions secret. This is required because a
repository-scoped `GITHUB_TOKEN` cannot dispatch a workflow in another
repository. Push the builder workflow first, add the secret, and then push
the source-repository dispatch workflow; that push will start the first
automatic build.

fastbuild adapted from https://github.com/tete1030/openwrt-fastbuild-actions
