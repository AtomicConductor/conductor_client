# Install client tools.

To install the Conductor client tools, choose an installer from the list below. If you are working in a shared environment, it is recommended that you install manually in a shared location and set a few environment variables for your studio.

### Downloads.

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

### To run an installer.

- Choose the appropriate link to download an installer for your operating system.

- Run the installer. Your system is set up and ready to submit jobs to Conductor. 

### To install manually.
 
Copy the downloaded source directory to a location of your choice and set the following environment variables. The examples below use Bash, and Powershell for Windows. You should adjust for your chosen environment.

``` bash fct_label="Mac"
export CONDUCTOR_LOCATION="/path/to/conductor_client"
# Python
export PYTHONPATH="${PYTHONPATH}:${CONDUCTOR_LOCATION}:${CONDUCTOR_LOCATION}/installers/osx/python/lib/python2.7/site-packages"
# Maya
export XBMLANGPATH=${CONDUCTOR_LOCATION}/conductor/resources:${XBMLANGPATH}
export MAYA_SHELF_PATH="${CONDUCTOR_LOCATION}/maya_shelf"
# Nuke
export NUKE_PATH= "${NUKE_PATH}:${CONDUCTOR_LOCATION}/nuke_menu"
# Conductor command line utilities
export PATH="${CONDUCTOR_LOCATION}/bin:$PATH"
```

``` bash fct_label="Linux" 
export CONDUCTOR_LOCATION="/path/to/conductor_client"
# Python
export PYTHONPATH="${PYTHONPATH}:${CONDUCTOR_LOCATION}:${CONDUCTOR_LOCATION}/python/lib/python2.7/site-packages"
# Maya
export XBMLANGPATH=${CONDUCTOR_LOCATION}/conductor/resources:${XBMLANGPATH}
export MAYA_SHELF_PATH="${CONDUCTOR_LOCATION}/maya_shelf"
# Nuke
export NUKE_PATH= "${NUKE_PATH}:${CONDUCTOR_LOCATION}/nuke_menu"
# Conductor command line utilities
export PATH="${CONDUCTOR_LOCATION}/bin:$PATH"
```

``` powershell fct_label="Windows"
$Env:CONDUCTOR_LOCATION = "C:\path\to\conductor_client"
# python
$Env:PYTHONPATH += ";$Env:CONDUCTOR_LOCATION"
$Env:PYTHONPATH += ";$Env:CONDUCTOR_LOCATION\installers\windows\python\Lib\site-packages"
# Maya
$Env:XBMLANGPATH+="$Env:CONDUCTOR_LOCATION\conductor\resources"
$Env:MAYA_SHELF_PATH+="$Env:CONDUCTOR_LOCATION\maya_shelf"
# Nuke
$Env:NUKE_PATH = "$Env:CONDUCTOR_LOCATION\nuke_menu"
# Conductor command line utilities
$Env:Path += ";$Env:CONDUCTOR_LOCATION/bin"
```



### Troubleshooting

If you are having trouble with the installation, here are some steps and suggestions to help you debug.

* Lorem ipsum, or lipsum as it is sometimes known, is dummy text used in laying out print.
* The passage is attributed to an unknown typesetter in the 15th century who.
* Cicero's De Finibus Bonorum et Malorum for use in a type specimen book.