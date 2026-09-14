# Experimental XGS-PON build profile

This profile lives on the builder's `q1000k-xgspon` branch. It uses the normal
Q1000K image selection plus the controller, vendor MAC/PHY, generic OMCI core,
`q1000k-omci` command, diagnostics, LuCI, supervisor and inactive DHCP/DHCPv6 WAN
packages. `CONFIG_BROKEN=y` exposes the experimental packages. It does not
change the source's disabled PON device-tree nodes, supply OEM firmware or
calibration, invent subscriber credentials, or enable the supervisor/WAN.

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
