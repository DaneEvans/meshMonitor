"""
Login UI module for multi-user authentication.
"""
from nicegui import ui
from typing import Callable, Optional
from gui.user_manager import UserManager


class LoginUI:
    """Handles the login user interface."""
    
    def __init__(self, user_manager: UserManager, on_login_success: Callable[[str], None]):
        """
        Initialize the login UI.
        
        Args:
            user_manager: Instance of UserManager for authentication
            on_login_success: Callback function to call when login is successful (receives username)
        """
        self.user_manager = user_manager
        self.on_login_success = on_login_success
        self.container = None
        self.username_input = None
        self.password_input = None
        self.error_label = None
        self.register_section = None
        self.show_register = False
    
    def setup(self) -> None:
        """Setup the login UI."""
        ui.page_title('MeshMonitor - Login')
        
        with ui.column().classes('w-full h-screen items-center justify-center bg-primary'):
            self.container = ui.card().classes('w-full max-w-md')
            
            with self.container:
                with ui.column().classes('w-full gap-4'):
                    # Header
                    ui.label('MeshMonitor').classes('text-h3 text-center')
                    ui.label('Meshtastic Network Monitor').classes('text-subtitle1 text-center text-gray-400')
                    
                    with ui.separator().classes('my-2'):
                        pass
                    
                    # Login form
                    with ui.column().classes('w-full gap-2') as login_form:
                        ui.label('Login').classes('text-h6')
                        
                        self.username_input = ui.input('Username').classes('w-full')
                        self.password_input = ui.input('Password', password=True, password_toggle_button=True).classes('w-full')
                        
                        # Error message
                        self.error_label = ui.label('').classes('text-red-500 text-caption')
                        self.error_label.visible = False
                        
                        # Login button
                        ui.button('Login', on_click=self._handle_login).classes('w-full')
                        
                        # Toggle to registration
                        with ui.row().classes('w-full justify-center'):
                            ui.label('Don\'t have an account?').classes('text-caption')
                            ui.link('Register', target='#', on_click=self._toggle_register).classes('text-caption text-blue-400')
                    
                    # Registration form (initially hidden)
                    with ui.column().classes('w-full gap-2') as register_form:
                        self.register_section = register_form
                        register_form.visible = False
                        
                        ui.label('Create Account').classes('text-h6')
                        
                        new_username_input = ui.input('Username').classes('w-full')
                        new_password_input = ui.input('Password', password=True, password_toggle_button=True).classes('w-full')
                        confirm_password_input = ui.input('Confirm Password', password=True, password_toggle_button=True).classes('w-full')
                        
                        register_error = ui.label('').classes('text-red-500 text-caption')
                        register_error.visible = False
                        
                        def handle_register():
                            new_username = new_username_input.value.strip()
                            new_password = new_password_input.value
                            confirm_password = confirm_password_input.value
                            
                            # Validation
                            if not new_username:
                                register_error.set_text('Username cannot be empty')
                                register_error.visible = True
                                return
                            
                            if len(new_username) < 3:
                                register_error.set_text('Username must be at least 3 characters')
                                register_error.visible = True
                                return
                            
                            if new_username in self.user_manager.get_all_users():
                                register_error.set_text('Username already exists')
                                register_error.visible = True
                                return
                            
                            if not new_password:
                                register_error.set_text('Password cannot be empty')
                                register_error.visible = True
                                return
                            
                            if len(new_password) < 6:
                                register_error.set_text('Password must be at least 6 characters')
                                register_error.visible = True
                                return
                            
                            if new_password != confirm_password:
                                register_error.set_text('Passwords do not match')
                                register_error.visible = True
                                return
                            
                            # Register the user
                            if self.user_manager.add_user(new_username, new_password):
                                register_error.set_text('Account created! Logging in...')
                                register_error.classes('text-green-500', remove='text-red-500')
                                register_error.visible = True
                                
                                # Auto-login after brief delay
                                def auto_login():
                                    if self.user_manager.authenticate(new_username, new_password):
                                        self.on_login_success(new_username)
                                
                                ui.timer(0.5, auto_login, once=True)
                            else:
                                register_error.set_text('Registration failed')
                                register_error.visible = True
                        
                        ui.button('Register', on_click=handle_register).classes('w-full')
                        
                        # Toggle back to login
                        with ui.row().classes('w-full justify-center'):
                            ui.label('Already have an account?').classes('text-caption')
                            ui.link('Login', target='#', on_click=self._toggle_register).classes('text-caption text-blue-400')
    
    def _toggle_register(self) -> None:
        """Toggle between login and registration forms."""
        self.show_register = not self.show_register
        # Find the login and register forms and toggle them
        children = self.container.get_container_elements()
        
        # Simple approach: clear and recreate the form
        # This is a workaround - in production you'd track form elements better
        for child in self.container.get_container_elements():
            if hasattr(child, 'visible'):
                if 'Login' in str(getattr(child, 'text', '')):
                    child.visible = not self.show_register
                elif 'Register' in str(getattr(child, 'text', '')):
                    child.visible = self.show_register
    
    def _handle_login(self) -> None:
        """Handle the login button click."""
        username = self.username_input.value.strip()
        password = self.password_input.value
        
        if not username or not password:
            self.error_label.set_text('Username and password required')
            self.error_label.visible = True
            return
        
        if self.user_manager.authenticate(username, password):
            self.error_label.visible = False
            self.on_login_success(username)
        else:
            self.error_label.set_text('Invalid username or password')
            self.error_label.visible = True
            self.password_input.value = ''
