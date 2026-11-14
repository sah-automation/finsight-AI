# 08: Add partition existence gate to upload path

**What to build:** Modify upload endpoint/path to check if partition exists for the company before accepting uploads. Return clear "partition missing" message if not. This is the critical gate - a company without partition cannot upload.

**Blocked by:** 07: Add onboarding API endpoint with System Admin authz

**Status:** ready-for-agent

- [ ] Find or create upload endpoint entrypoint
- [ ] Check partition exists via PartitionManager/partition metadata
- [ ] Reject with clear "partition missing" message if not exists
- [ ] Enforce upload form fields per ADR-0004 (upload_type new/update only, no delete action)
- [ ] Ensure company_id is enforced
