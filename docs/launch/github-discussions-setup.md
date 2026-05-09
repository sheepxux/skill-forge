# Enable GitHub Discussions for skill-forge

Discussions can't be enabled from the CLI alone (the `gh` API call requires `repo` scope and the right token type). The fastest path is the web UI — about 60 seconds total.

## One-time setup (web UI)

1. Open https://github.com/sheepxux/skill-forge/settings (Settings tab on the repo, not your profile).
2. Scroll to **Features**.
3. Tick **Discussions**.
4. Click **Set up discussions**.
5. GitHub asks you to pick a starter template — pick **General announcement**, you can edit it after.

## Recommended category layout

After the starter template lands, click **Discussions → ⚙️ Manage** in the top-right of the Discussions tab, then create these categories:

| Category | Format | Purpose |
| --- | --- | --- |
| **📣 Announcements** | Announcement | Release notes, ClawHub publishes, breaking changes |
| **💡 Skill Showcase** | Open-ended discussion | Users share skills they forged. The point of this category is to make Skill Forge feel like a community artifact, not a solo project |
| **❓ Q&A** | Q&A | Install issues, signed-gate questions, profile selection help |
| **🛠️ Design Discussion** | Open-ended discussion | HMAC trade-offs, replay scoring fidelity, profile-pack proposals |
| **🐛 Bug Reports** | Open-ended discussion | Lower-friction than Issues; convert to Issues when triaged |

## Seed posts to write on day one

A new Discussions tab with zero posts looks dead. Write these three before you announce:

1. **📣 Announcements → "v1.3.0 'Benchmark Pipeline' is live"** — link to ClawHub + GitHub release.
2. **💡 Skill Showcase → "Show us what you've forged"** — pin it; explain the post template (skill name, profile, what it solves, link to the candidate).
3. **🛠️ Design Discussion → "Should the HMAC secret default fall back to bot-token derivation?"** — open with the same trade-off you wrote in the Show HN. Invites real engagement.

## Optional: convert existing Issues to Discussions

For any open issue that is really a question or a design conversation, click **... → Convert to discussion** in the issue header. Keeps the Issues tab focused on actual defects.

## Optional: gh-cli automation for repeat tasks

Once Discussions is on, the `gh` CLI can post into it without browser:

```bash
# List categories to get the category ID
gh api graphql -f query='{
  repository(owner:"sheepxux", name:"skill-forge") {
    discussionCategories(first:10) {
      nodes { id name slug }
    }
  }
}'

# Create a discussion (replace category id and repo id)
gh api graphql -f query='
  mutation($repo:ID!,$cat:ID!,$title:String!,$body:String!) {
    createDiscussion(input:{
      repositoryId:$repo, categoryId:$cat, title:$title, body:$body
    }) { discussion { url } }
  }
' -f repo=R_kgDO... -f cat=DIC_kwDO... -f title="..." -f body="..."
```

Useful if you want to mirror release notes from CI into Announcements automatically.
