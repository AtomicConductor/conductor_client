'''
exceptions module

This module handles all custom exceptions for the Conductor Client Tools
All exceptions should at minimum inherit off of the Exception base class
'''

class UserCanceledError(Exception):
    '''
    Custom Exception to indicate that the user cancelled their action
    '''