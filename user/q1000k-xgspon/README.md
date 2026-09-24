# Experimental XGS-PON build profile

The normal `quantum_q1000k-ubi` target on the source's `q1000k-xgspon`
branch now integrates PON and produces both initramfs recovery and SquashFS
sysupgrade FITs. Its base configuration explicitly selects both formats.
Use the default `experimental` profile with this branch for the normal pair;
`bench` and `activation` below remain separate RAM-only targets. The source's
`target/linux/airoha/XGSPON-NORMAL-IMAGES.q1000k.md` documents normal-image
factory data, shared firmware, external private RAM patches and its `scripts/q1000k/image-build.py` local build wrapper.
The main builder and `q1000k-dev` remain unchanged.

For the separate NAND-disabled, TX-inhibited RAM bench, pass `--profile bench`
to `prepare`. It selects `quantum_q1000k-xgspon-bench`, enables OpenWrt's
IMAGEOPT/PREINITOPT gates and sets both normal LAN and preinit/failsafe to
`192.168.0.1/24`. The bench package disables LAN DHCP, DHCPv6 and RA servers.
Use a dedicated host address such as `192.168.0.2/24`; 192.168.1.1 is the
user's working router and must not be used for Q1000K SSH. Verification
rejects lost IP settings, a selected normal UBI profile or squashfs output.
No automatic PON startup, firmware flash or hardware testing is performed.

The bench target produces only its initramfs FIT. Check the exact image with
the source repository's `tests/q1000k/check_pon_bench_image.py`. It validates
FIT hashes, embedded initramfs, NAND/PCS exclusions, controller TX inhibit,
network defaults and absent PON module autoload. Read the source repository's
`target/linux/airoha/XGSPON-BENCH.q1000k.md` for staged runtime tests and the
calibration/firmware inputs kept outside the generic image.

This profile lives on the builder's `q1000k-xgspon` branch. It uses the normal
Q1000K image selection plus the controller, vendor MAC/PHY, generic OMCI core,
`q1000k-omci` command, diagnostics, LuCI, supervisor and DHCP/DHCPv6 WAN
packages. The normal device on the integrated source branch enables the
required PON nodes. Generic builds include the shared OEM firmware pair and read each unit's
identity/calibration from UBI factory. Subscriber registration and any ISP
settings must be configured before service activation; no private data is
embedded in generic images. The
explicit package selections and `CONFIG_BROKEN=y` remain compatible with
older experimental source checkpoints; current Q1000K packages no longer
require that Kconfig gate.

The existing workflows and `user/q1000k/settings.ini` still select
`q1000k-dev`. This profile has no automatic workflow, release, upload or device
connection. Normal build caches and source checkouts are not reused.

## Prepare a pinned build

Run from this builder checkout. Select a full source commit on
`q1000k-xgspon` that contains all of the profile's packages, and choose a new
directory whose parent already exists:

```sh
python3 scripts/q1000k-xgspon-build.py prepare \
  --revision FULL_40_CHARACTER_SOURCE_COMMIT \
  /path/to/new-xgspon-build
```

For an unpushed local source checkpoint, also pass
`--repo /path/to/openwrt-q1000k`. The helper clones only the experimental
branch, checks ancestry, checks out the exact revision detached, verifies the
package sources and writes the combined `.config`, `files/build_info` and
`selection.json`. It refuses an existing destination. A failed preparation
may leave a diagnostic checkout but never publishes a success manifest.

Install the normal OpenWrt build prerequisites, then prepare the source feeds
and resolve the Kconfig selections:

```sh
cd /path/to/new-xgspon-build/openwrt
./scripts/feeds update -a
./scripts/feeds install -a
make defconfig
```

Before compilation, run the helper from this builder checkout:

```sh
python3 scripts/q1000k-xgspon-build.py verify /path/to/new-xgspon-build
```

Verification rejects a changed HEAD, tracked or untracked source edits, missing package
sources, a changed profile/manifest, and dependencies that silently removed a
required configuration symbol. Then compile in the prepared source checkout
using the normal `make download` and `make -jN` commands. Verify again before
using the artifacts. Record the resolved `.config`, `selection.json`, feed
revisions and artifact checksums with build results; pinning OpenWrt alone does
not pin the separately fetched feeds. Git-ignored inputs such as feeds and a
user-provided `files/` overlay are outside the source-edit check and must be
recorded separately. The helper supplies only `files/build_info`.

The current work permits **read-only device access and never flashing**.
Building these packages is not hardware acceptance or authorization to boot,
install, flash or activate them. The source's XGS-PON status document records
the remaining hardware and service capability limits.

## Local checks

`python3 tests/test_xgspon_build.py` uses temporary Git repositories to test
branch/revision selection, source isolation, configuration rejection and
preservation of existing paths. It performs no network or device operation.
The real OpenWrt Kconfig graph must also retain every selection; the helper's
`verify` command checks the resulting configuration after `make defconfig`.
