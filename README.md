# Q1000K builder

This project automates builds of the OpenWrt initramfs and sysupgrade images
for the Quantum Fiber Q1000K.

The workflows build the `quantum_q1000k` device from
[`lightingghost/openwrt-q1000k`](https://github.com/lightingghost/openwrt-q1000k)
on its `main` branch. Each release contains exactly these artifacts:

- `*-quantum_q1000k-initramfs-uImage.itb`
- `*-quantum_q1000k-squashfs-sysupgrade.bin`

The source branch must define both Q1000K images before a workflow is run.
Dispatch the toolchain workflow, then the base-image workflow, before the
first firmware workflow. The release step deliberately fails if either
expected artifact is missing, instead of publishing an incomplete firmware
release.

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
