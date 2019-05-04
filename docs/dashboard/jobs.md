---
title: Jobs
summary: Dashboard jobs page.
authors:
    - Julian Mann
date: 2019-05-02
---

# Jobs.

## Introduction

The Conductor submitter for Jobs allows you to ship renders to Conductor's cloud from a familiar interface within Jobs. It is implemented as a custom class that lives inside the project. The class name is ConductorJob.

You may configure many ConductorJobs in a single project in order to try out different cloud parameters. A single job may also be set up to render many images, such as multiple VR cameras.

Any properties you set on a ConductorJob will be stored inside the project when you save, so you can be confident that subsequent renders of the same scene will behave the same.

## Installation

If you haven't already done so, [install Conductor client tools](../install.md) now. 
 
## Register the plugin
To register the submitter, set the provided startup script in the prefereces panel. It will take effect the next time you start Jobs.

`$CONDUCTOR_LOCATION/conductor/clarisse/startup.py`

![prefs][prefs]


!!!note ""
    To avoid a restart, enter the following in the script editor:

    `from conductor.clarisse import startup`

Once the plugin is registered, you should see ConductorJob in the **Create** menu, and in the **New** menu when you right click over a browser. If not, refer to [installation troubleshooting](../install.md#troubleshooting).


## Quick start

#### To create a submission to Conductor:
* Open a scene containing one or more images to be rendered.
* Select the **project** context.
* In the right mouse menu, go to **New > ConductorJob**.

![new][new]

You'll now see a ConductorJob item in the attribute editor. 

!!!note ""
    You can hover over any attribute name to get a detailed description of its purpose and behavior.

* Set a title for your job. This will show up on the Conductor dashboard.
* Click **Add** in the Images section to choose some images to be rendered.

![titleimage][titleimage]

If you haven't done so already, turn on **Render To Disk** for each image and set a filename in the **Save As** attribute.

You'll notice the project is **- not set -** and the pulldown menu is empty. This is because the submitter has not yet been in contact with your account at Conductor. 

* Press the **Refresh** button at the top of the attribute editor and if prompted, sign in to Conductor.
* Choose a project from the **Project** drop-down menu.
* In the Frames section, turn on **Use Custom Frames** and enter `1-10` in the **Custom Frames** field.
* Set **Chunk Size** to 2.
* Turn on **Use Scout Frames** and enter `3,8` in **Scout Frames** field.

You'll notice the **Frames Info** attribute has updated to let you know which frames will be submitted, and how many will be scouted first. 

![frames][frames]

* If you have some idea of the machine specification needed for your images, choose it in the **Instance Type** drop-down menu.
* Check that your version of Jobs appears in the **Packages** attribute. If it hasn't been detected, you'll need to open the **Choose Packages** panel and choose a suitable version.

You are now ready to submit your render using either the **Submit** or **Preview** buttons, which you'll find at the top of the attribute editor. You are encouraged to use the **Preview** button, which will allow you to first check the parameters that will be submitted.


![preview][preview]


If everyting looks good, press the **Submit** button.



[preview]: ../image/clarisse/preview.png
[titleimage]: ../image/clarisse/titleimage.png
[prefs]: ../image/clarisse/prefs.png
[new]: ../image/clarisse/new.png
[frames]: ../image/clarisse/frames.png
