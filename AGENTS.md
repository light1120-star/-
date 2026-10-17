# Repository skills

This repository contains self-installed skills in `.agents/skills/<skill-name>/`.
Read the selected skill's SKILL.md before using it. Local credentials and system/plugin skills are not distributed.

## Relocated packages

The original handraw-style package is now `.agents/skills/handdraw-style-prompter`.
The original nuwa-skill package is now `.agents/skills/huashu-nuwa`.
When upstream instructions mention those old local directories, resolve them to these repository directories. Other package names map to their identically named folders.
Each nested skill also has its own top-level folder matching its declared name. Nested `SKILL.reference.md` files preserve the original package resources without creating duplicate skill registrations.
Relative file references within a skill resolve against that skill directory. If a reference assumes the original package layout, consult the corresponding retained package tree above.
Browser extensions, local speech credentials, desktop applications, and external connectors are not installed by copying this library; verify the required runtime capability before executing such a workflow.
