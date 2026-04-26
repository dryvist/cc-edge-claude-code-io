# Claude Code Pack For Edge

## Overview

This Cribl Edge pack collects Claude Code telemetry from two sources and forwards it to a Cribl Stream worker group for indexing, analysis, and search:

1. **Session logs** — Monitors the Claude Code projects directory for `.jsonl` conversation transcript files and ships them in real time.
2. **OpenTelemetry (OTLP)** — Receives metrics and logs from Claude Code's built-in OTEL instrumentation via gRPC on port 4317.

## Installation

Download the latest `.crbl` artifact from the [GitHub Releases page](https://github.com/dryvist/cc-edge-claude-code-io/releases) and import it into your Cribl Edge fleet via the UI: **Manage → Packs → Add Pack → Upload Pack File**.

Then proceed to the per-input setup sections below ([Session Logs](#setup-session-logs-file-monitor) and/or [OpenTelemetry](#setup-opentelemetry-otlp)) — you can enable one or both depending on your needs.

## Usage

After importing the pack, no further configuration is required for the Cribl side. Each event flows:

1. **In** through one of the two inputs (file monitor or OTLP gRPC), tagged with the appropriate `datatype`.
2. **Through** its matching pipeline, which sets Splunk-canonical `sourcetype`, `index`, and `datatype` fields via an Eval function (see [Pipeline tagging](#pipeline-tagging)).
3. **Out** via the Edge fleet's global Send-to-Routes output to your downstream destination (typically Cribl Stream → Splunk).

The full architecture diagram, source/route/pipeline reference, and per-platform troubleshooting are documented in the sections below.

## Architecture

```
Claude Code (CLI) ──writes──▶ ~/.claude/projects/**/*.jsonl
       │                                 │
       │                      Cribl Edge (file monitor)
       │                                 │
       └──OTLP/gRPC:4317──▶ Cribl Edge (OpenTelemetry source)
                                         │
                              Cribl HTTP ──▶ Cribl Stream Worker Group
```

## Data Sources

This pack collects two distinct types of data from Claude Code. You can enable one or both depending on your needs.

### Session Logs (File Monitor)

The file monitor input reads the `.jsonl` transcript files that Claude Code writes to disk during every conversation. These contain the **full content** of each session — what the user asked, what Claude responded, which tools were invoked, and what they returned. Use this data for:

- **Audit and compliance** — Complete record of every interaction
- **Session replay** — Reconstruct exactly what happened in a conversation
- **Content analysis** — Search across prompts, responses, and tool outputs
- **Cost tracking** — Per-session model usage, token counts, and USD cost from summary events

### OpenTelemetry (OTLP)

The OTLP input receives **operational telemetry** pushed directly from Claude Code's built-in OpenTelemetry instrumentation over gRPC. This is structured metrics and logs — not conversation content. Use this data for:

- **Observability dashboards** — API latency, error rates, throughput
- **Resource monitoring** — Token consumption trends, model usage patterns
- **Alerting** — Detect anomalies in cost, latency, or error rates
- **Fleet-wide visibility** — Aggregate telemetry across multiple developers or hosts

### Choosing Between Them

```
Session Logs (File Monitor)
───────────────────────────────────────────────────
What it captures         Full conversation content (prompts, responses, tool calls)
Data format              JSONL (one JSON object per line)
Collection method        Cribl Edge reads files from disk
Best for                 Audit, compliance, session replay, content search
Permissions needed       Filesystem read access to ~/.claude/projects/
Contains PII             Yes

OpenTelemetry (OTLP)
───────────────────────────────────────────────────
What it captures         Operational metrics and instrumented logs
Data format              OTLP (standard OpenTelemetry protocol)
Collection method        Claude Code pushes telemetry over gRPC
Best for                 Dashboards, alerting, performance monitoring
Permissions needed       Network access to port 4317
Contains PII             No
```

---

## Requirements

- **Cribl Edge** 4.17.0+
- **Claude Code** installed for the local user
- **Supported platforms:** Linux, macOS (Sonoma 14+, Sequoia 15+, Tahoe 26), Windows (Server 2016/2019/2022, Windows 10/11)
- **Filesystem permissions:** The Cribl Edge process must have read access to `~/.claude/projects/` and its contents (if using the file monitor input)
- **Port 4317** available for the OTLP gRPC listener (if using the OpenTelemetry input)

---

## Setup: Session Logs (File Monitor)

The file monitor input requires two things: an environment variable telling Cribl Edge where the session logs live, and filesystem permissions so the Cribl Edge process can read them.

### Step 1: Set the `CLAUDE_HOME` Environment Variable

The file monitor path uses `$CLAUDE_HOME` to resolve the correct session log directory. This variable must be set in the Cribl Edge environment. Restart the Cribl service after setting it.

> Note: replace `<user>` with the user that runs Claude Code.

#### Linux

```bash
export CLAUDE_HOME=/home/<user>/.claude/projects/
```

#### macOS

```bash
export CLAUDE_HOME=/Users/<user>/.claude/projects/
```

#### Windows

Set the environment variable for the Cribl Edge service. You can do this during MSI installation or via the system environment:

```powershell
# PowerShell (run as Administrator)
[System.Environment]::SetEnvironmentVariable("CLAUDE_HOME", "C:\Users\<user>\.claude\projects\", "Machine")
```

Or add it via **System Properties > Environment Variables > System variables**.

> After setting the variable, restart the Cribl Edge service for it to take effect.

```
Platform                 Session Log Path
─────────────────────────────────────────────────────────
Linux                    /home/{user}/.claude/projects/
macOS                    /Users/{user}/.claude/projects/
Windows                  C:\Users\{user}\.claude\projects\
```

> **Note:** Some recent Claude Code versions on Linux may use `~/.config/claude/projects/` instead. Verify which directory contains your `.jsonl` session files before configuring the input.

### Step 2: Grant Filesystem Permissions

Claude Code creates `.jsonl` files with restrictive permissions. The approach to granting Cribl Edge read access differs by platform.

#### Linux

Cribl Edge typically runs as the `cribl` user. Since Claude Code creates files with mode `0600` (owner-only), POSIX ACLs are required to grant read access without changing file ownership.

**Directory ACLs:**

```bash
# Grant cribl user access to traverse to the projects directory
setfacl -m u:cribl:r-x /home/<user>/.claude
setfacl -m u:cribl:r-x /home/<user>/.claude/projects

# Set default ACLs so new subdirectories inherit permissions
setfacl -R -d -m u:cribl:r-x /home/<user>/.claude/projects/
setfacl -R -d -m m::r-x /home/<user>/.claude/projects/
```

**File ACL Mask Fix:**

Claude Code creates files with mode `0600`, which sets the POSIX ACL mask to `---` and nullifies all ACL grants. Fix existing files and directories:

```bash
# Fix mask on files (r-- is sufficient for regular files)
find /home/<user>/.claude/projects/ -type f -exec setfacl -m m::r {} +

# Fix mask on directories (r-x needed for traversal)
find /home/<user>/.claude/projects/ -type d -exec setfacl -m m::r-x {} +
```

**Cron Job for New Files:**

Since Claude Code will keep creating files with mode `0600`, add a cron job to periodically fix ACL masks on new `.jsonl` files. This cron entry must be added to the **`cribl` user's** crontab (not root), so the ACL changes are applied in the correct user context:

```bash
# Edit the cribl user's crontab
sudo crontab -u cribl -e

# Add this entry (runs every 5 minutes)
*/5 * * * * find /home/<user>/.claude/projects/ -type f -name "*.jsonl" ! -perm /g+r -exec setfacl -m m::r {} + 2>/dev/null
```

**Verification:**

```bash
# Confirm cribl user can read a session file
sudo -u cribl cat /home/<user>/.claude/projects/<project>/<session-id>.jsonl | head -1

# Check that ACL mask is r-- (not ---) on .jsonl files
getfacl /home/<user>/.claude/projects/<project>/<session-id>.jsonl | grep mask
# Expected: mask::r--
```

#### macOS

On macOS, Cribl Edge is typically installed under the current user account (not a separate `cribl` service user). If Edge is running as the same user that owns the Claude Code session files, no additional permission changes are needed.

If Edge runs as a different user, grant read access using macOS ACLs:

```bash
# Grant the cribl user read access to the projects directory
chmod +a "cribl allow read,readattr,readextattr,readsecurity,list,search" /Users/<user>/.claude
chmod +a "cribl allow read,readattr,readextattr,readsecurity,list,search" /Users/<user>/.claude/projects

# Apply recursively to existing contents
chmod -R +a "cribl allow read,readattr,readextattr,readsecurity,list,search" /Users/<user>/.claude/projects/
```

> **Note:** macOS does not support POSIX ACL masks the way Linux does. The `chmod +a` syntax is macOS-specific (uses the NFSv4 ACL model). A periodic `launchd` job or cron entry may still be needed if new files are created with restrictive permissions.

**Verification:**

```bash
# List ACLs on the projects directory
ls -le /Users/<user>/.claude/projects/

# Test read access (if running Edge as a different user)
sudo -u cribl cat /Users/<user>/.claude/projects/<project>/<session-id>.jsonl | head -1
```

#### Windows

On Windows, Cribl Edge runs as the `LocalSystem` account by default. `LocalSystem` has broad read access to local files, so in most cases no additional permissions are required.

If Cribl Edge is configured to run under a custom service account, grant that account read access to the Claude Code projects directory:

```powershell
# PowerShell (run as Administrator)
$path = "C:\Users\<user>\.claude\projects"
$acl = Get-Acl $path
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "<SERVICE_ACCOUNT>", "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow"
)
$acl.AddAccessRule($rule)
Set-Acl $path $acl
```

Or use `icacls` from an elevated command prompt:

```cmd
icacls "C:\Users\<user>\.claude\projects" /grant "<SERVICE_ACCOUNT>:(OI)(CI)RX" /T
```

**Verification:**

```powershell
# Check effective permissions
icacls "C:\Users\<user>\.claude\projects"

# Test that the Cribl service can read a session file
Get-Content "C:\Users\<user>\.claude\projects\<project>\<session-id>.jsonl" -First 1
```

---

## Setup: OpenTelemetry (OTLP)

The OTLP input is preconfigured in the pack and listens on port 4317 out of the box — no Cribl-side setup is needed. You just need to configure Claude Code to send telemetry to it.

Set the following environment variables in the shell where you run Claude Code:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRIC_EXPORT_INTERVAL=60000
export OTEL_LOGS_EXPORT_INTERVAL=5000
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta
```

```
Variable                                              Description
─────────────────────────────────────────────────────────────────────────────────────────
CLAUDE_CODE_ENABLE_TELEMETRY                          Enables Claude Code's built-in OTel instrumentation
OTEL_EXPORTER_OTLP_ENDPOINT                           OTLP collector endpoint (Cribl Edge OTLP source)
OTEL_EXPORTER_OTLP_PROTOCOL                           Transport protocol (grpc)
OTEL_METRICS_EXPORTER                                 Metrics exporter type (otlp)
OTEL_LOGS_EXPORTER                                    Logs exporter type (otlp)
OTEL_METRIC_EXPORT_INTERVAL                           Metrics flush interval in ms (default: 60000)
OTEL_LOGS_EXPORT_INTERVAL                             Logs flush interval in ms (default: 5000)
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE     Metrics temporality (delta)
```

> **Tip:** Add these exports to your shell profile (`.bashrc`, `.zshrc`, etc.) so they persist across sessions. If Cribl Edge is running on a remote host, replace `localhost` with the appropriate hostname or IP.

---

## Pack Components

These are preconfigured in the pack. This section is for reference — no action is needed here unless you want to customize the defaults.

### Input: `Session-Logs-File-Monitor`

- **Type:** File Monitor
- **Path:** Resolves via `$CLAUDE_HOME`
- **Filter:** `*.jsonl`
- **Recursive:** Yes
- **Poll interval:** 10 seconds
- **Metadata:** `datatype == 'claude-code-session-logs'`

Monitors all Claude Code session transcript files. Each `.jsonl` file represents a single conversation session and contains structured JSON events (messages, tool calls, tool results, file snapshots, etc.).

### Input: `claude-code-otel`

- **Type:** OpenTelemetry (`open_telemetry`)
- **Protocol:** gRPC
- **Host:** `0.0.0.0`
- **Port:** `4317`
- **TLS:** Disabled
- **Auth:** None
- **OTLP Version:** 1.3.1
- **Max active connections:** 1000
- **Metadata:** `datatype == ''claude-code-otel'`

Receives OTLP telemetry (metrics and logs) directly from Claude Code over gRPC.

### Route: Session Logs (File Monitor)

- **Filter:** `datatype=='claude-code-session-logs'`
- **Pipeline:** `claude-code-session-logs`
- **Output:** `__group` (Send to Fleet Routes)

### Route: OpenTelemetry (OTLP)

- **Filter:** `datatype=='claude-code-otel'`
- **Pipeline:** `claude-code-otel`
- **Output:** `__group` (Send to Fleet Routes)

### Pipeline tagging

Both pipelines run an Eval function that sets Splunk-canonical fields on every event before forwarding:

| Pipeline | sourcetype | index | datatype |
|---|---|---|---|
| `claude-code-otel` | `claude:code:otel` | `claude-code` | `claude-code-otel` |
| `claude-code-session-logs` | `claude:code:session_logs` | `claude-code` | `claude-code-session-logs` |

Adjust these per your Splunk index naming conventions if needed (edit `default/pipelines/<name>/conf.yml`).

> **Note:** This pack sends all events to the global route table via **Send to Routes**. Configure your destination
  (Splunk, S3, Elastic, etc.) in the fleet's global routes and outputs

---

## Reference: Session Log Event Types

Each line in a `.jsonl` session log file is a standalone JSON object. Most event types share a common envelope with fields like `sessionId`, `uuid`, `timestamp`, `cwd`, and `type`. The `assistant` and `user` events additionally carry an API-shaped `message` object with `content` blocks and `usage` telemetry.

### Top-Level Event Types

Identified by the `type` field on each JSON object:

```
Type                     Description
─────────────────────────────────────────────────────────
assistant                Claude's response turns (text, tool invocations, token usage)
user                     User messages and tool results (stdout/stderr) returned to Claude
summary                  Conversation summary metadata (model, token counts, cost, turns, duration)
file-history-snapshot    File state checkpoints for session undo/restore
system                   Internal system events (hook summaries, configuration signals)
progress                 Wrapper for real-time progress updates (see subtypes below)
queue-operation          Message queue lifecycle events (enqueue/dequeue)
```

### Progress Subtypes

`progress` events contain a `data.type` field that identifies the specific kind of progress update:

```
Subtype                  Description
─────────────────────────────────────────────────────────
agent_progress           Subagent (Task tool) execution progress and streamed responses
tool_result              Completed tool execution results returned to the model
hook_progress            User-configured hook lifecycle events (start, stop, output)
text                     Streamed text fragments during assistant response generation
bash_progress            Real-time output from long-running Bash tool commands
query_update             Web search query sent to a search provider
search_results_received  Web search results returned from a search provider
create                   File or resource creation events from tool execution
update                   File or resource modification events from tool execution
mcp_progress             MCP (Model Context Protocol) server tool execution progress
```

### Example Event (summary)

```json
{
  "type": "summary",
  "summary": {
    "model": "claude-opus-4-6",
    "inputTokens": 42531,
    "outputTokens": 1247,
    "totalCostUSD": 0.285,
    "numTurns": 8,
    "durationMs": 134520
  }
}
```

---

## Reference: OpenTelemetry Metrics and Events

Claude Code emits 13 telemetry signals over OTLP — 8 metrics and 5 events.

### Metrics

Exported via `OTEL_METRICS_EXPORTER`. These are numerical measurements collected at the interval defined by `OTEL_METRIC_EXPORT_INTERVAL`.

```
Metric                                Description
─────────────────────────────────────────────────────────────────────────────
claude_code.session.count              Number of Claude Code sessions started
claude_code.cost.usage                 Cost in USD incurred by API calls
claude_code.token.usage                Token consumption (input and output)
claude_code.active_time.total          Total active time spent in sessions
claude_code.lines_of_code.count        Lines of code written or modified
claude_code.code_edit_tool.decision    Code edit tool invocation decisions (accept/reject)
claude_code.pull_request.count         Pull requests created
claude_code.commit.count               Git commits created
```

### Events

Exported via `OTEL_LOGS_EXPORTER`. These are discrete log entries emitted when specific actions occur during a session.

```
Event                                  Description
─────────────────────────────────────────────────────────────────────────────
claude_code.user_prompt                User prompt submitted to Claude
claude_code.tool_result                Result returned from a tool execution
claude_code.api_request                API request sent to the Claude API
claude_code.api_error                  Error response received from the Claude API
claude_code.tool_decision              Model's decision to invoke a specific tool
```

---

## Troubleshooting

### File Monitor

**No events flowing:**

1. Verify `$CLAUDE_HOME` is set correctly and points to the right directory for your OS.
2. Check that the file monitor discovered files in the Cribl Edge logs.
3. Verify the route is not disabled in the Cribl UI.
4. Confirm the output destination is reachable.

**EACCES errors in worker log (Linux):**
The `cribl` user cannot read the `.jsonl` files. Run the ACL mask fix commands from the [Linux permissions](#linux) section and restart the Cribl Edge worker:

```bash
sudo -u cribl /opt/cribl/bin/cribl restart
```

**Access denied errors (Windows):**
If running Edge under a custom service account (not `LocalSystem`), apply the NTFS permissions from the [Windows permissions](#windows) section and restart the Cribl Edge service:

```powershell
Restart-Service CriblEdge
```

**Path separator issues (Windows):**
Ensure the `CLAUDE_HOME` variable uses backslashes (`\`) and not forward slashes. The File Monitor source on Windows expects native Windows paths.

**Stale file tracking:**
Cribl Edge tracks file state in its kvstore. If you need to re-ingest files from the beginning, stop the worker, clear the relevant kvstore directories, and restart.

- Linux/macOS: `/opt/cribl/state/kvstore/default/file_claude-code-logs*/`
- Windows: `C:\ProgramData\Cribl\state\kvstore\default\file_claude-code-logs*\`

### OpenTelemetry

**No OTLP telemetry arriving:**

1. Confirm `CLAUDE_CODE_ENABLE_TELEMETRY=1` is set in the Claude Code shell environment.
2. Verify `OTEL_EXPORTER_OTLP_ENDPOINT` points to the correct Cribl Edge host and port (`http://localhost:4317`).
3. Check that port 4317 is not blocked by a firewall or already in use by another process.
4. Inspect the Cribl Edge worker logs for connection or parsing errors on the OTLP source.
5. Verify the `claude-code-otel` input is not disabled in the Cribl UI.

---

## Release Notes

Release-please proposes versions automatically via PR; see the [GitHub Releases page](https://github.com/dryvist/cc-edge-claude-code-io/releases) for the canonical version history once the first release lands. No releases have been cut yet.

## Authors

* Andrew Hendrix - <Andrewh@VisiCoreTech.com>
* Jacob Evans - <jevans@VisiCoreTech.com>

To contact us, please email <CriblPacks@VisiCoreTech.com>.

## Contributing to the Pack

To contribute to this Pack, or to report any issues or enhancement requests, please connect with **VisiCore Tech** on [Cribl Community Slack](https://cribl-community.slack.com) or email us at: <CriblPacks@visicoretech.com>.

## License
---
This Pack uses the following license: [`Apache 2.0`](https://github.com/criblio/appscope/blob/master/LICENSE)