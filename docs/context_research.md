# Contextual Enhancements Research

This note summarizes feasible approaches for enriching transcription prompts with local context on macOS.

## Clipboard history

- macOS exposes only the latest clipboard item via `NSPasteboard.generalPasteboard()`. To maintain a history, the app must poll the pasteboard's `changeCount`, cache new values, and manage retention (for example a ring buffer of the last N entries).
- Implementation path:
  1. Use `pyobjc` to access the AppKit APIs from Python.
  2. Set up a background thread or timer that checks `changeCount` every ~200 ms.
  3. When the count increases, read the current textual content (`stringForType_` with `NSPasteboardTypeString`) and append it to an in-memory history structure, filtering out duplicates or very short entries.
  4. Persist only if the user opts in; clipboard data can be highly sensitive.
- Alternative: fall back to the command line utility `pbpaste` for single-shot reads, but it cannot deliver historical entries without our own caching.

## Active application context

- The foreground application can be discovered with `NSWorkspace.sharedWorkspace().frontmostApplication()` (available via `pyobjc`). The bundle identifier or localized app name can be injected into prompts to hint at domain-specific expectations, e.g., code editors vs. messaging apps.
- Window titles and selected text require Accessibility (AX) APIs:
  - Use `Quartz`'s `AXUIElementCreateApplication(pid)` to query the focused window or selected text.
  - The process must be granted "Accessibility" privileges in System Settings → Privacy & Security → Accessibility.
  - AX queries can be brittle; wrap them in defensive try/except blocks and add timeouts.

## Suggested integration flow

1. Create an opt-in "context collector" component that is started alongside the hotkey listener.
2. Maintain a short clipboard history (for example the last 5 non-empty text entries) and expose it as a list of strings.
3. Track the foreground application bundle id plus window title.
4. When preparing the Gemini transcription prompt, append a lightweight context section, for example:
   ```
   最近剪贴板:
   - …
   当前应用: Xcode (窗口: MyProject.swift)
   ```
   Keep the section concise (≤ 300 tokens) to avoid prompt inflation.
5. Provide a configuration flag so users can disable context collection or limit what is included.

## Privacy considerations

- Always request explicit consent before reading clipboard or Accessibility data.
- Avoid storing context on disk unless the user opts in; in-memory buffers should be cleared after each session.
- Provide a quick toggle (e.g., via CLI flag or config entry) to disable context enrichment at runtime.

These notes should make it straightforward to prototype a context helper module once we prioritise the feature.
