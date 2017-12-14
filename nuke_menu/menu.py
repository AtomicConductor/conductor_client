import os
import logging

# Wrap *ALL* in a try/except. *ANY* exception can prevent Nuke from successfully
# opening/launching. Don't want to break Nuke for customers!
try:
    import nuke

    from conductor import submitter

    PACKAGE_DIRPATH = os.path.dirname(submitter.__file__)
    RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
    CONDUCTOR_ICON_FILEPATH = os.path.join(RESOURCES_DIRPATH, 'conductor_logo_01_x32.png')

    def create_conductor_menu():
        menu = nuke.menu('Nuke').addMenu(name="Conductor",
                                         icon=CONDUCTOR_ICON_FILEPATH,
                                         tooltip="Conductor tools")

        menu.addCommand(name='Submitter UI',
                        command="import conductor;conductor.loadConfig();from conductor import submitter_nuke;submitter_nuke.NukeConductorSubmitter.runUi()",
                        tooltip="Launch the Conductur Submitter UI")

        return menu

    conductor_menu = create_conductor_menu()
except:
    logging.exception("Failed to load Conductor menu:\n")
