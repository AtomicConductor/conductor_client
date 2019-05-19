#Docs on docs

This documentation project contains _technical_ documentation for public facing Conductor components. Internal documentation for ther components is beyond scope.

## Setup

Conductor documentation is built on [mkdocs][2].
It uses the Windmill theme, and some code formatting plugins.

`pip install mkdocs mkdocs-windmill pygments markdown-fenced-code-tabs`

The setup consists of a `mkdocs.yml` file and a `docs` folder in the root of the repo.

To start the server locally:

* From the root of the repo enter `mkdocs serve`
* View the site at **127.0.0.1:8000**




## Write docs

### Grammar

#### General guidelines.

Follow the Google [developer documentation style guide][3].

#### Conductor terminology.

To save time, we should find ways to express Conductor concepts consistently. that are particular to Conductor or clloud rendering. e.g. 
_At Conductor, Your account at Conductor, on Conductor's servers??_

#### What to document.

* Most documentation can be split into: 
    - **Getting started:** Help the user get a result as fast as possible.
    - **Reference:** Node referenece, API reference.
    - **Concept discussion:** e.g. _Choosing an instance type to minimize costs._ 
* The doc site doesn't eliminate the need for contextual documentation like tooltips etc.
* Don't document:
    * Obvious features.
    * Things any normal computer user should know.
    * Things unrelated to Conductor. e.g. Docker. Provide links if necessary.
* Consider the option to improve UX to make it obvious, rather than document it. 


#### Test.
 
* Scan the doc. Can you make a mental index? 
* Omit <del>needless</del> words. -- <cite>[Steve Krug][1]</cite>
 
## Publish

The docs are hosted on Github Pages. 

To publish:

* From the root of the repo enter `mkdocs gh-deploy`. 
* To see the updates, head over to [our github pages site][4]



### Workflow

#### Responsibilities

* The dev who writes code is responsible for documenting it.
* Code reviewers should check the docs reflect the changes.

#### Build and Deploy

Consider these constraints:

* Documentation lives alongside the code it refers to.
* Public facing code lives in at least 2 repositories.
* The documentation site should be built as one site.
* Publishing should be automatic.

There are 2 conventional ways to build with Github pages:

* [Project Pages][5]. Docs are in the same repo as the code.
* [User and Organization Pages][6]. The docs live in their own repo.

 <span style="color:red">How do we resolve this?</span>

## Formatting examples

### Images 


![diag][diag]
 

### Code hilighting and fenced tabs 

This is the `autumn` css theme for pygments. There are plenty of others.

Fencing is achieved by making a series of uninterrupted blocks of code.


```python
"""Provide UI to specify what events to notify users of.

Currently only email notifications.
"""

import re
import ix

# Simple loose email regex, matches 1 email address.
SIMPLE_EMAIL_RE = re.compile(r"^\S+@\S+$")

def handle_email_addresses(obj, _):
    """Validate email addresses when attribute changes."""
    val = obj.get_attribute("email_addresses").get_string().strip(',').strip()
    result = bool(val)
    for address in [x.strip() for x in val.split(',')]:
        if not SIMPLE_EMAIL_RE.match(address):
            result = False
            break
    if not result:
        ix.log_warning("Email addresses are invalid.")

```

```bash
#export MAYA_DEBUG_ENABLE_CRASH_REPORTING=1
export MAYA_APP_DIR=$HOME/maya
export MAYA_VERSION="2018"
export MAYA_MODULE_PATH=${MAYA_MODULE_PATH}:${MAYA_APP_DIR}/modules

 # maya functions
#########################################
function curr_maya_project() {
    local maya_prj_list=`cat "${MAYA_APP_DIR}/${MAYA_VERSION}/prefs/userPrefs.mel" | grep RecentProjectsList |sed "s/\"//g"`
    local curr_maya_prj=`echo $maya_prj_list | awk  '{print $NF}'` 
    echo $curr_maya_prj
}
alias mp='cd `curr_maya_project`'
alias llrm='echo "Paste ls -l output for files to delete. ^D when done"; \rm -rf `awk '\''{print $9}'\''`' # remove by pasting from long list output
```

```json
{
  "autoretry_policy": {
    "preempted": {
      "max_retries": 3
    }
  },
  "max_instances": 0,
  "notify": null,
  "output_path": "/Users/julian/projects/fish/clarisse_fish/images/jobA",
  "upload_paths": [
    "/Users/julian/projects/fish/clarisse_fish/arch_shading.project",
    "/Users/julian/projects/fish/maya_fish/cache/alembic/fish_100.abc"
  ]
}
```

```docker
FROM gcr.io/eloquent-vector-104019/conductor_docker_base:7abb26b9-3bf2-4927-846f-ed15460046ea

RUN apt-get update && apt-get install -y bzip2
# RUN echo "deb http://http.debian.net/debian/ jessie main" >   /etc/apt/sources.list && \
WORKDIR /work

ADD ./silhouettev7_Silhouette-v7.0.11.tgz  ./
COPY   ./install.py ./
RUN python install.py
ENV PATH /opt/silhouette7.0.11:$PATH
```
 


### Tables


|Release label  |  Operating system| Download link | 
|:------------|:-------------|:-------------|
|Stable |Centos el7 installer|  [conductor-v2.7.100-0.el7.x86_64.rpm](https://github.com/AtomicConductor/conductor_client/releases/download/v2.7.100/conductor-v2.7.100-0.el7.x86_64.rpm) |
|Stable |Windows 10 installer|  [conductor-v2.7.100.exe](https://github.com/AtomicConductor/conductor_client/releases/download/v2.7.100/conductor-v2.7.100.exe) |
|Stable |Mac installer|  [conductor-v2.7.100.pkg](https://github.com/AtomicConductor/conductor_client/releases/download/v2.7.100/conductor-v2.7.100.pkg) |
|Stable |Manual install|  [v2.7.100.tar.gz](https://github.com/AtomicConductor/conductor_client/archive/v2.7.100.tar.gz) |
|Clarisse beta |Centos el7 installer|  [conductor-v2.8.5-0.el7.x86_64.rpm](https://github.com/AtomicConductor/conductor_client/releases/download/v2.8.5/conductor-v2.8.5-0.el7.x86_64.rpm) |
|Clarisse beta |Windows 10 installer|  [conductor-v2.8.5.exe](https://github.com/AtomicConductor/conductor_client/releases/download/v2.8.5/conductor-v2.8.5.exe) |
|Clarisse beta |Mac installer|  [conductor-v2.8.5.pkg](https://github.com/AtomicConductor/conductor_client/releases/download/v2.8.5/conductor-v2.8.5.pkg) |
|Clarisse beta |Manual install|  [v2.8.5.tar.gz](https://github.com/AtomicConductor/conductor_client/archive/v2.8.5.tar.gz) |
|All conductor-client releases|All|  [Github releases page](https://github.com/AtomicConductor/conductor_client/releases) |


### Notes and special panels

!!!note
    You can hover over any attribute name to get a detailed description of its purpose and behavior.

!!! warning
    Don't go out in this town after 9:30pm.

!!! danger
    You are likely to cause considerable damage if you touch this button.

 
### Misc

* For strikethrough, use `<del>word</del>` or `<s>word</s>` as tildes dont work.
 

[1]:https://www.amazon.com/Dont-Make-Think-Revisited-Usability/dp/0321965515/ref=dp_ob_title_bk
[2]:https://www.mkdocs.org/
[3]:https://developers.google.com/style/highlights
[4]:https://atomicconductor.github.io/conductor_client/
[5]:https://help.github.com/articles/user-organization-and-project-pages/#project-pages-sites
[6]:https://help.github.com/articles/user-organization-and-project-pages/#user-and-organization-pages-sites

[diag]: image/diag.png
