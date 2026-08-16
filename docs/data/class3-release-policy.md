# Class 3 release-policy gate

This offline artifact is not public-release approval. The example policy is
fail-closed (`approval_status=not_approved`), so every scope is blocked.
`candidate_released` means only that an approved internal test policy passed
static rules; it is never external publication approval.

The gate reads verified serving marts and, only for dominance evaluation,
checksum-verified monthly facts. It never reads Excel or checkpoint SQLite.
It publishes canonical, atomic status artifacts without raw endpoint IDs,
individual amounts, shares, or numerators/denominators.

Differencing-attack protection is currently `not_implemented`; that state
cannot produce a public candidate. Current operation remains local/internal API
only. Before any public service, institutions must separately approve thresholds,
minority-cell suppression, dominance definitions, differencing protection,
authentication, audit, and deployment. A future public-facing API must enforce
this artifact; this PR does not create one.
