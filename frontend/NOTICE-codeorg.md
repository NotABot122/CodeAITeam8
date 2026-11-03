# Attribution: Code.org

Parts of this front end are adapted from Code.org's adaptive pathway front end
in <https://github.com/code-dot-org/code-dot-org> (`apps/src/adaptive/`),
which is licensed under the Apache License, Version 2.0.

Each adapted file carries a header naming its source file. We rewrote those
files for our schema and dropped their dependencies on Code.org internals
(`@cdo/apps/*`, Redux, FontAwesome, the Quiz components); the logic that
survives is the dependency-depth layout of a prerequisite graph and the
one-question-at-a-time answer flow.

Changes from the originals are stated in each file header.

Not used: Code.org's artwork, graphics, logos, fonts, and screenshots. Their
LICENSE excludes these ("Proprietary Materials") and we have not copied any.
Keep it that way: do not add assets from that repository here.

Apache License 2.0: <https://www.apache.org/licenses/LICENSE-2.0>
