import hou
def doit(node):
    print("submit")
    # try:
    #     if hou.hipFile.hasUnsavedChanges():
    #         save_file_response = hou.ui.displayMessage(
    #             "There are some unsaved changes. Do you want to save the file before "
    #             "submitting to Conductor?", buttons=("Yes", "No", "Cancel"), close_choice=2)
    #         if save_file_response == 2:
    #             return
    #         if save_file_response == 0:
    #             hou.hipFile.save()
    #     hou.ui.displayMessage(text='Job submitted')
    #     print('Job submitted')
    # except Exception as e:
    #     hou.ui.displayMessage(text=str(e), title='Job submission failed')

