
![diag][diag]


### Code hilighting

This is the `autumn` theme. There are plenty of others.

#### Python

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

def notify_changed(obj, attr):
    """Dim the email field based on toggle value."""
    obj.get_attribute("email_addresses").set_read_only(not attr.get_bool())

class PackageTreeItem(ix.api.GuiTreeItemBasic):
    """An item in the tree that maintains its own child list."""

    def __init__(self, parent, name):
        ix.api.GuiTreeItemBasic.__init__(self, parent, name)
        self.child_list = []
        self.was_selected = False
```

#### Bash

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

#### Json

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


#### Docker

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



[diag]: image/diag.png
