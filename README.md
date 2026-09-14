# ConnectWiz — natural language contact center analytics for Amazon Quick Desktop

An Amazon Quick Desktop skill that lets contact center analysts query Amazon Connect data, CloudWatch call flow logs, flow configuration, and cost data through natural language — using Model Context Protocol (MCP) to correlate insights across the four sources.

> ⚠️ This is sample code, for demonstration purposes only — it is not intended for production use without further review and hardening. Have your security and legal teams review this sample before using it in a production or customer-facing setting.

## Install

1. **Code → Download ZIP** on this repository.
2. In Amazon Quick Desktop, add a custom skill and upload that zip.
3. Connect the **AWS MCP server** as a user MCP server, if it is not already:

   ```json
   {
     "mcpServers": {
       "aws-mcp": {
         "command": "uvx",
         "transport": "stdio",
         "timeout": 100000,
         "args": [
           "mcp-proxy-for-aws-cli@latest",
           "https://aws-mcp.us-east-1.api.aws/mcp",
           "--metadata",
           "AWS_REGION=us-west-2"
         ]
       }
     }
   }
   ```

4. Ask it something. With no arguments it produces the full four-tab dashboard.

## What's here

| Path | |
|---|---|
| `SKILL.md` | The whole program. A prompt artifact, not code — no build step, no test suite, no dependency manifest. |
| `references/dashboard_template.html` | Authoritative dashboard layout. Apache ECharts is inlined, so a generated dashboard makes zero external requests. |
| `references/dashboard_style.md` | Visual rules and per-metric color thresholds. |
| `scripts/connectwiz_render.py` | Template-fill renderer. Runs under plain `python3`. |

## AWS access

**This skill instructs the model to issue only read operations** — it queries Athena, CloudWatch
Logs, the Amazon Connect API, and Cost Explorer, and the only side effect it intends is Athena query
results landing in your own configured S3 output location.

That is an instruction, not a technical control. The skill is a prompt, and it runs on the AWS MCP
server, which forwards requests to AWS **using your credentials** and whose tools can execute any
AWS API operation those credentials allow — including writes. **Whether this skill can modify
anything in your account is determined entirely by the IAM policy you attach, not by the skill.**
Treat the skill as untrusted input to your own authorization decisions and grant it least privilege.

AWS provides controls built for this. The condition keys `aws:ViaAWSMCPService` and
`aws:CalledViaAWSMCP` let an identity-based policy or SCP allow reads while denying mutating actions
specifically when a request arrives through an AWS-managed MCP server. See:

- [Identity and access management for AWS MCP Server](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/security-iam.html)
- [Identity-based policy examples for AWS MCP Server](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/security_iam_id-based-policy-examples.html)
- [Understanding IAM for managed AWS MCP servers](https://aws.amazon.com/blogs/security/understanding-iam-for-managed-aws-mcp-servers/)

## Known limitations

- **IVR containment is an upper bound, not a measurement.** Contact-trace data cannot distinguish a caller who self-served from one who gave up — both disconnect in the flow, so both count as contained.
- **Architecture detection classifies but does not yet change any formula.** It is wired for it; nothing downstream varies by it.
- **Cost figures carry their account scope.** Cost Explorer returns the calling account's view — organization-wide from a payer account, single-account from a member. An unlabeled total can be wrong by an unknowable multiple.
- **Sankey inputs must be acyclic.** Real contact flows loop; loops are split into separately named nodes rather than drawn as back-edges, so a "loop" node is a real path and not a rendering artifact.

## Third-party content

`references/dashboard_template.html` bundles **Apache ECharts 5.5.1** (Apache License 2.0,
© The Apache Software Foundation, https://echarts.apache.org/), which itself embeds **ZRender**
(Apache-2.0, https://github.com/ecomfe/zrender). Both license headers travel inline with the
minified code and must not be stripped. Nothing else third-party is distributed here — the
template uses a local monospace font stack rather than a webfont.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
