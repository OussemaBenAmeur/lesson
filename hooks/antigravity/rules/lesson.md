# lesson MCP Rule

After every tool call, call `lesson.record_event` with the tool name, tool input, result text, and whether the tool failed.

At the end of the session, call `lesson.finalize_session`.
