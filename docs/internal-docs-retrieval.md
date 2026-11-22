# Internal docs and SOP retrieval

`search_internal_docs` searches Markdown and text files under the repository's
`docs/` directory. It returns short excerpts, relative paths, line ranges, and
citations such as `[local-startup.md:L71-L79]`. It does not search chat memory,
Attic, workspace files, or arbitrary filesystem paths. Documents are read-only
reference material; instructions inside a document are not executable policy.

Agent-core scans at most 1,000 Markdown/text files, skips symlinks and files
over 1 MB, and uses a lightweight local lexical ranker. The index is cached in
process memory and refreshed when file size or modification time changes. The
WhatsApp/Telegram agent can search during a conversation; web admins can query
it through the authenticated API.

```text
GET  /admin/docs/search?query=deployment+rollback&limit=5
POST /admin/docs/reindex
```

Both endpoints require `x-admin-api-key`. Docker mounts `docs/` read-only into
agent-core. Recreate the service after deploying the mount change.
