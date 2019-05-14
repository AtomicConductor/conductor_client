This doc project will contain documentation for all public facing Conductor components, not just client tools.

Grammar
Try to follow Google developer documentation style guide.
https://developers.google.com/style/highlights

Conductor specific writing style.
Word choices for concepts should be consistent where possible. In most cases use the same names as in the DB

instance / machine / vm / remote computer / server

In many cases you'll need to talk about sending things to Conductor. I can be difficult getting the terminology right.
For example:
Send X to Conductor
Send X to your acocunt at Conductor
Send X to Conductor's servers.
Send X to Conductor's cloud.

We need to discover what works and then be consistent

Uses https://www.mkdocs.org/ framework, so you need to install

mkdocs                                     
Pygments


-- To start the server

`mkdocs serve` from the root of the repo (same location as as mkdocs.yaml)

-- To build

`mkdocs build` although this will eventually be handled by CICD 
