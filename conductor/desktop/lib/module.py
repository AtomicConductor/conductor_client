from Qt import QtGui, QtCore, QtWidgets


class DesktopModule(QtWidgets.QWidget):
    '''
    Module

    - instantiate widget
    - add to navbar 
    - menu name
    - menu index
    https://stackoverflow.com/a/37233643

    '''

    def getNavbarName(self):
        pass

    def getNavbarVisible(self):
        pass

    def getNavbarIndex(self):
        pass


#     def load_plugin(filename, context):
#         source = open(filename).read()
#         code = compile(source, filename, 'exec')
#         exec(code, context)
#         return context['func']
#
#         context = {'func_one': func_one, 'func_two': func_two, 'abc': abc}
#         func = load_plugin(filename, context)
#         func()
