# KCH Helical v0.17.6 — current ComCat location-uncertainty vintage

This gate refreshes the public USGS/FDSN location-uncertainty crosswalk under the
same frozen matching and 0.80 both-error coverage threshold used by v0.14.3.

ComCat is a mutable observation service. The 2026-10-12 responses are therefore a
**new vintage**. Historical response hashes and the v0.14.3 crosswalk hash are
recorded for comparison but are not required to match.

The immutable mechanism/fault inputs, blind selection and selected indices must
still match exactly. The gate is non-directional: it never opens strike/dip/rake,
does not access the sealed-test partition as such, fits no model and executes no
v0.17 null job. All raw catalogue and row-level crosswalk material is purged before
receipts are persisted.

PASS binds the new location-uncertainty vintage to v0.17.5.2. It authorizes only a
separate successor that may regenerate TRAIN+CALIBRATION rows and execute the
already-qualified v0.17 runtime while maintaining a physical firewall against
sealed-test values.
