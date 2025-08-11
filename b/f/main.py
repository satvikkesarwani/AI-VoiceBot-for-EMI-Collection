# main.py - Main Kivy Application File

import os
import json
import requests
import threading
from kivy.clock import Clock
from datetime import datetime
from functools import partial


# Kivy Core Imports
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform, get_color_from_hex
from kivy.lang import Builder
from kivy.storage.jsonstore import JsonStore
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition

# Kivy UI Components & Properties
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.animation import Animation
import logging
# Configure basic logging (outputs to console; you can adjust level/file as needed)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from kivy.graphics.texture import Texture
from kivy.properties import (
    StringProperty,
    ListProperty,
    BooleanProperty,
    ObjectProperty,
    NumericProperty
)

# --- Custom Widget Definitions ---
# These classes are needed for the Kivy language files to work correctly.

class HoverBehavior(object):
    """Adds hover functionality to a widget."""
    hovering = BooleanProperty(False)
    border_point = None

    def __init__(self, **kwargs):
        self.register_event_type('on_enter')
        self.register_event_type('on_leave')
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(HoverBehavior, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return
        pos = args[1]
        inside = self.collide_point(*self.to_widget(*pos))
        if self.hovering == inside:
            return
        self.border_point = pos
        self.hovering = inside
        if inside:
            self.dispatch('on_enter')
        else:
            self.dispatch('on_leave')

    def on_enter(self, *args):
        pass

    def on_leave(self, *args):
        pass

class ModernSwitch(ButtonBehavior, FloatLayout):
    """A visually appealing toggle switch."""
    active = BooleanProperty(False)
    _track_color_active = ListProperty(get_color_from_hex('#4361ee'))
    _track_color_inactive = ListProperty(get_color_from_hex('#6c757d'))
    _thumb_color = ListProperty(get_color_from_hex('#f8f9fa'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._update_thumb_pos)

    def on_active(self, instance, value):
        self._update_thumb_pos()

    def on_press(self):
        self.active = not self.active

    def _update_thumb_pos(self, *args):
        if self.active:
            pos = (self.right - self.ids.thumb.width - dp(4), self.y + dp(4))
        else:
            pos = (self.x + dp(4), self.y + dp(4))
        
        anim = Animation(pos=pos, duration=0.15, t='out_quad')
        anim.start(self.ids.thumb)

class GlassyCard(BoxLayout):
    pass

class GlassyTextInput(TextInput):
    pass

class CardLayout(BoxLayout):
    pass

class RoundedButton(Button):
    pass

class CustomTextInput(TextInput):
    pass

class IconButton(HoverBehavior, Button):
    pass

class IconLabelButton(HoverBehavior, ButtonBehavior, BoxLayout):
    pass

class GlassyButton(HoverBehavior, Button):
    _color_normal = ListProperty([0, 0, 0, 1])
    _color_down = ListProperty([0, 0, 0, 1])
    scale = NumericProperty(1.0)
    is_active = BooleanProperty(False)

    _gradient_color_1 = ListProperty([0, 0, 0, 1])
    _gradient_color_2 = ListProperty([0, 0, 0, 1])
    _active_color = ListProperty([0, 0, 0, 1])
    _inactive_color = ListProperty([0, 0, 0, 1])

    def _create_gradient(self, color1, color2):
        if not color1 or not color2 or self.width <= 0 or self.height <= 0:
            return Texture.create(size=(1, 1))

        texture = Texture.create(size=(int(self.width), int(self.height)), colorfmt='rgba')
        buf = bytearray()
        for x in range(int(self.width)):
            for y in range(int(self.height)):
                mix_ratio = x / float(self.width)
                r = color1[0] * (1.0 - mix_ratio) + color2[0] * mix_ratio
                g = color1[1] * (1.0 - mix_ratio) + color2[1] * mix_ratio
                b = color1[2] * (1.0 - mix_ratio) + color2[2] * mix_ratio
                a = color1[3] * (1.0 - mix_ratio) + color2[3] * mix_ratio
                buf.extend([int(c * 255) for c in (r, g, b, a)])
        
        texture.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
        return texture
# -------------------------------------------------

# Set window size for desktop testing
if platform != 'android':
    Window.size = (360, 640)

class APIManager:
    """Handles all API communications with the Flask backend"""
    def update_bill_paid_status(self, bill_id, new_status, callback):
        def _update_status():
            try:
                response = requests.put(
                    f"{self.base_url}/bills/{bill_id}/status",
                    json={'is_paid': new_status},
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_update_status).start()
    
    def __init__(self):
        self.base_url = "http://127.0.0.1:5000/api"
        self.token = None
        self.store = JsonStore('bills_reminder.json')
        self.load_token()
    
    def load_token(self):
        if self.store.exists('auth'):
            self.token = self.store.get('auth')['token']
    
    def save_token(self, token):
        self.token = token
        self.store.put('auth', token=token)
    
    def clear_token(self):
        self.token = None
        if self.store.exists('auth'):
            self.store.delete('auth')
    
    def get_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    def register(self, email, password, name, phone_number, callback):
        def _register():
            try:
                response = requests.post(
                    f"{self.base_url}/auth/register",
                    json={
                        'email': email,
                        'password': password,
                        'name': name,
                        'phone_number': phone_number
                    },
                    headers={'Content-Type': 'application/json'}
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_register).start()
    
    def login(self, email, password, callback):
        def _login():
            try:
                response = requests.post(
                    f"{self.base_url}/auth/login",
                    json={'email': email, 'password': password},
                    headers={'Content-Type': 'application/json'}
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_login).start()
    
    def get_bills(self, callback):
        def _get_bills():
            try:
                response = requests.get(
                    f"{self.base_url}/bills",
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_get_bills).start()
    
    
    
    def update_bill(self, bill_id, bill_data, callback):
        def _update_bill():
            try:
                response = requests.put(
                    f"{self.base_url}/bills/{bill_id}",
                    json=bill_data,
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_update_bill).start()
    
    def delete_bill(self, bill_id, callback):
        def _delete_bill():
            try:
                response = requests.delete(
                    f"{self.base_url}/bills/{bill_id}",
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_delete_bill).start()
    
    def mark_bill_paid(self, bill_id, callback):
        def _mark_paid():
            try:
                response = requests.post(
                    f"{self.base_url}/bills/{bill_id}/pay",
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_mark_paid).start()
    
    def send_test_reminder(self, reminder_type, callback):
        def _send_reminder():
            logging.info(f"Starting API call for test reminder type: {reminder_type}")
            try:
                response = requests.post(
                    f"{self.base_url}/reminders/test",
                    json={'type': reminder_type},
                    headers=self.get_headers()
                )
                logging.info(f"API call completed for test reminder type: {reminder_type}. Status: {response.status_code}")
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                logging.error(f"Error in API call for test reminder type: {reminder_type}: {str(e)}")
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_send_reminder).start()
    
    def get_reminder_settings(self, callback):
        def _get_settings():
            try:
                response = requests.get(
                    f"{self.base_url}/reminders/settings",
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_get_settings).start()
    
    def update_reminder_settings(self, settings, callback):
        def _update_settings():
            try:
                response = requests.put(
                    f"{self.base_url}/reminders/settings",
                    json=settings,
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)
        
        threading.Thread(target=_update_settings).start()
        
    
       
    def create_bill(self, bill_data, callback):
        """Create new bill and its associated loan details in one call."""
        def _create_bill():
            try:
                # Makes a single API call with the combined bill and loan data
                response = requests.post(
                    f"{self.base_url}/bills",
                    json=bill_data,
                    headers=self.get_headers()
                )
                Clock.schedule_once(lambda dt: callback(response), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback(None, err), 0)

        threading.Thread(target=_create_bill).start()

class LoginScreen(Screen):
    pass

class RegisterScreen(Screen):
    pass

class DashboardScreen(Screen):
    bills_data = ListProperty([])
    
    def on_enter(self):
        self.load_bills()
        self.update_nav_buttons()

    def update_nav_buttons(self):
        current_screen = self.manager.current
        
        self.ids.btn_home.is_active = False
        self.ids.btn_add.is_active = False
        self.ids.btn_settings.is_active = False
        
        
        if current_screen == 'dashboard':
            self.ids.btn_home.is_active = True
        elif current_screen == 'add_bill':
            self.ids.btn_add.is_active = True
        elif current_screen == 'settings':
            self.ids.btn_settings.is_active = True
        
    
    def load_bills(self):
        app = App.get_running_app()
        app.api.get_bills(self.on_bills_loaded)
    
    def on_bills_loaded(self, response, error=None):
        if error:
            self.show_error("Failed to load bills")
            return
        
        if response and response.status_code == 200:
            self.bills_data = response.json()
            self.update_bills_display()
        else:
            self.show_error("Failed to load bills")
    
    def update_bills_display(self):
        bills_list = self.ids.bills_list
        bills_list.clear_widgets()
        
        if not self.bills_data:
            bills_list.add_widget(Label(
                text="No users found\nTap + to add your first user",
                size_hint_y=None,
                height=dp(100),
                halign='center'
            ))
            return
        
        for bill in self.bills_data:
            bill_item = BillItem()
            bill_item.bill_data = bill
            bills_list.add_widget(bill_item)
    
    def show_error(self, message):
        popup = Popup(
            title='Error',
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()

class BillItem(BoxLayout):
    bill_data = ObjectProperty({})
    
    def on_bill_data(self, instance, value):
        if value:
            self.ids.account_name.text = value.get('account_name', 'No Account')
            self.ids.bill_name.text = value.get('name', '')
            self.ids.bill_amount.text = f"₹{value.get('amount', 0)}"
            due_date = value.get('due_date', '')
            if due_date:
                try:
                    date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    self.ids.bill_due_date.text = date_obj.strftime('%d %b %Y')
                except:
                    self.ids.bill_due_date.text = due_date
            
            is_paid = value.get('is_paid', False)
            self.ids.status_label.text = 'PAID' if is_paid else 'PENDING'
            self.ids.status_label.color = (0, 0.7, 0, 1) if is_paid else (1, 0, 0, 1)
    
    def mark_as_paid(self):
        app = App.get_running_app()
        bill_id = self.bill_data.get('id')
        if bill_id:
            app.api.mark_bill_paid(bill_id, self.on_paid_response)
    
    def on_paid_response(self, response, error=None):
        app = App.get_running_app()
        if response and response.status_code == 200:
            app.root.get_screen('dashboard').load_bills()
        else:
            app.show_popup('Error', 'Failed to mark bill as paid')
            
    def edit_bill(self):
        app = App.get_running_app()
        app.root.get_screen('add_bill').bill_data = self.bill_data
        app.root.get_screen('add_bill').is_edit_mode = True
        app.root.current = 'add_bill'
    
    def delete_bill(self):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text='Are you sure you want to delete this bill?'))
        
        buttons = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        cancel_btn = Button(text='Cancel')
        delete_btn = Button(text='Delete', background_color=(1, 0, 0, 1))
        
        buttons.add_widget(cancel_btn)
        buttons.add_widget(delete_btn)
        content.add_widget(buttons)
        
        popup = Popup(
            title='Confirm Delete',
            content=content,
            size_hint=(0.8, 0.3)
        )
        
        cancel_btn.bind(on_release=popup.dismiss)
        delete_btn.bind(on_release=lambda x: self.confirm_delete(popup))
        
        popup.open()
    
    def confirm_delete(self, popup):
        popup.dismiss()
        app = App.get_running_app()
        bill_id = self.bill_data.get('id')
        if bill_id:
            app.api.delete_bill(bill_id, self.on_delete_response)
    
    def on_delete_response(self, response, error=None):
        app = App.get_running_app()
        if response and response.status_code == 204:
            app.root.get_screen('dashboard').load_bills()
        else:
            app.show_popup('Error', 'Failed to delete bill')
    # In the BillItem class in main.py

# ... (other methods) ...

    def toggle_paid_status(self):
        app = App.get_running_app()
        bill_id = self.bill_data.get('id')
        if bill_id:
            current_status = self.bill_data.get('is_paid', False)
            new_status = not current_status
            app.api.update_bill_paid_status(bill_id, new_status, self.on_paid_response)

class AddBillScreen(Screen):
    bill_data = ObjectProperty({})
    is_edit_mode = BooleanProperty(False)
    loan_details_card = ObjectProperty(None)

    def on_switch_toggle(self, switch, switch_id):
        """Handle toggle button state changes."""
        # This is a placeholder method that prevents the AttributeError.
        print(f"Switch '{switch_id}' toggled to state: {switch.active}")

    def on_kv_post(self, base_widget):
        self.loan_details_card = self.ids.loan_details_card

    
    
    def on_enter(self):
        if self.is_edit_mode and self.bill_data:
            self.populate_form()
        else:
            self.clear_form()
    
    def populate_form(self):
        self.ids.bill_name.text = self.bill_data.get('name', '')
        self.ids.bill_amount.text = str(self.bill_data.get('amount', ''))
        self.ids.bill_category.text = self.bill_data.get('category', 'utilities')
        self.ids.bill_frequency.text = self.bill_data.get('frequency', 'monthly')
        self.ids.bill_notes.text = self.bill_data.get('notes', '')
        self.ids.account_name.text = self.bill_data.get('account_name', '')
        
        reminder_prefs = self.bill_data.get('reminder_preferences', {})
        self.ids.enable_call_switch.active = reminder_prefs.get('enable_call', False)
        
        due_date = self.bill_data.get('due_date', '')
        if due_date:
            try:
                date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                self.ids.bill_due_date.text = date_obj.strftime('%Y-%m-%d')
            except:
                self.ids.bill_due_date.text = ''
    
    def clear_form(self):
        self.ids.bill_name.text = ''
        self.ids.bill_amount.text = ''
        self.ids.bill_due_date.text = ''
        self.ids.bill_category.text = 'utilities'
        self.ids.bill_frequency.text = 'monthly'
        self.ids.bill_notes.text = ''
        self.ids.account_name.text = ''
        self.bill_data = {}
        self.is_edit_mode = False
        self.ids.enable_call_switch.active = False

        # --- ADD THESE LINES TO CLEAR THE LOAN FIELDS ---
        self.ids.loan_total_amount.text = ''
        self.ids.loan_monthly_payment.text = ''
        self.ids.loan_installments.text = ''
        self.ids.loan_already_paid.text = '0'  # Reset to default
        self.ids.loan_interest_rate.text = '0' # Reset to default
        # --------------------------------------------------

        # Resets the screen state
        self.bill_data = {}
        self.is_edit_mode = False
    
    def save_bill(self):
        """Save or update bill, now with mandatory loan details."""
        # --- Main Fields Validation ---
        required_fields = {
            'Account Name': self.ids.account_name.text,
            'Bill Name': self.ids.bill_name.text,
            'Amount': self.ids.bill_amount.text,
            'Due Date': self.ids.bill_due_date.text
        }
        for name, value in required_fields.items():
            if not value:
                self.show_error(f"Please fill in the '{name}' field.")
                return

        # --- Loan Fields Validation ---
        required_loan_fields = {
            'Total Loan Amount': self.ids.loan_total_amount.text,
            'Monthly EMI': self.ids.loan_monthly_payment.text,
            'Total Installments': self.ids.loan_installments.text
        }
        for name, value in required_loan_fields.items():
            if not value:
                self.show_error(f"Please fill in the '{name}' field.")
                return

        try:
            # --- Prepare the combined data payload ---
            bill_data = {
                'account_name': self.ids.account_name.text,
                'name': self.ids.bill_name.text,
                'amount': float(self.ids.bill_amount.text),
                'due_date': self.ids.bill_due_date.text + 'T00:00:00Z',
                'category': 'loan',  # Hardcode category to 'loan'
                'frequency': self.ids.bill_frequency.text,
                'notes': self.ids.bill_notes.text,
                'reminder_preferences': {
                    'enable_call': self.ids.enable_call_switch.state == 'down',
                },
                # Embed loan details directly into the main payload
                'loan_details': {
                    'total_amount': float(self.ids.loan_total_amount.text),
                    'monthly_payment': float(self.ids.loan_monthly_payment.text),
                    'total_installments': int(self.ids.loan_installments.text),
                    'installments_paid': int(self.ids.loan_already_paid.text or 0),
                    'interest_rate_percent': float(self.ids.loan_interest_rate.text or 0)
                }
            }
        except ValueError:
            self.show_error("Invalid number format in Amount or Loan Details.")
            return

        app = App.get_running_app()
        if self.is_edit_mode and self.bill_data.get('id'):
            # Update logic will need to be adjusted if you support editing loans
            app.api.update_bill(self.bill_data['id'], bill_data, self.on_save_response)
        else:
            app.api.create_bill(bill_data, self.on_save_response)
    
    def on_save_response(self, response, error=None):
        if error:
            self.show_error(f"Failed to save bill: {error}")
            return
        
        if response and response.status_code in [200, 201]:
            app = App.get_running_app()
            app.root.current = 'dashboard'
            app.root.get_screen('dashboard').load_bills()
        else:
            error_msg = "Failed to save bill."
            if response:
                try:
                    error_msg += f" (Status {response.status_code}: {response.json().get('message', 'Unknown error')})"
                except json.JSONDecodeError:
                    error_msg += f" (Status {response.status_code}: {response.text})"
            self.show_error(error_msg)
    
    def show_error(self, message):
        popup = Popup(
            title='Error',
            content=Label(text=message, halign='center'),
            size_hint=(0.8, 0.3)
        )
        popup.open()

# In the SettingsScreen class in main.py

class SettingsScreen(Screen):

    def save_settings_on_toggle(self, switch):
        """
        Callback method to save settings immediately when a toggle button is pressed.
        This prevents the AttributeError from the .kv file.
        """
        self.save_settings()
    def on_enter(self):
        app = App.get_running_app()
        app.api.get_reminder_settings(self.on_settings_loaded)
    
    def on_settings_loaded(self, response, error=None):
        if response and response.status_code == 200:
            settings = response.json()
            # FIX: Set the state based on the boolean value from the server.
            self.ids.whatsapp_switch.state = 'down' if settings.get('whatsapp_enabled', False) else 'normal'
            self.ids.call_switch.state = 'down' if settings.get('call_enabled', False) else 'normal'
            self.ids.sms_switch.state = 'down' if settings.get('sms_enabled', False) else 'normal'
            self.ids.notification_switch.state = 'down' if settings.get('local_notifications', True) else 'normal'
            self.ids.days_before_input.text = str(settings.get('days_before', 3))
            self.ids.preferred_time_input.text = settings.get('preferred_time', '09:00')

    def save_settings(self):
        # This method combines all the correct logic in a single, properly defined function.
        settings = {
            # FIX: Get the boolean value from the state property.
            'whatsapp_enabled': self.ids.whatsapp_switch.state == 'down',
            'call_enabled': self.ids.call_switch.state == 'down',
            'sms_enabled': self.ids.sms_switch.state == 'down',
            'local_notifications': self.ids.notification_switch.state == 'down',
            'days_before': int(self.ids.days_before_input.text or 3),
            'preferred_time': self.ids.preferred_time_input.text or '09:00'
        }
    
        app = App.get_running_app()
        app.api.update_reminder_settings(settings, self.on_settings_saved)

    def on_settings_saved(self, response, error=None):
        if error:
            App.get_running_app().show_popup('Error', 'Failed to save settings')
            return
        if response and response.status_code == 200:
            App.get_running_app().show_popup('Success', 'Settings saved successfully')
    
    def test_reminder(self, reminder_type):
        logging.info(f"Test reminder button pressed for type: {reminder_type}")
        app = App.get_running_app()
        app.api.send_test_reminder(reminder_type, self.on_test_reminder_response)
    
    def on_test_reminder_response(self, response, error=None):
        logging.info(f"Test reminder response received for type. Status: {response.status_code if response else 'None'}, Error: {error}")
        app = App.get_running_app()
        if response and response.status_code == 200:
            app.show_popup('Success', 'Test reminder sent successfully')
        else:
            app.show_popup('Error', 'Failed to send test reminder')
    
    def logout(self):
        app = App.get_running_app()
        app.api.clear_token()
        app.root.current = 'login'

class BillsReminderApp(App):
    
    def build(self):
        self.api = APIManager()
        self.title = 'Bills Reminder'
        Builder.load_file('styles.kv')
        Builder.load_file('auth_screens.kv')
        Builder.load_file('dashboard_screen.kv')
        Builder.load_file('add_bill_screen.kv')
        Builder.load_file('settings_screen.kv')
        
        
        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(RegisterScreen(name='register'))
        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(AddBillScreen(name='add_bill'))
        sm.add_widget(SettingsScreen(name='settings'))
        
        if self.api.token:
            sm.current = 'dashboard'
        else:
            sm.current = 'login'
        
        return sm
    
    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def login(self, email, password):
        if not email or not password:
            self.show_popup('Error', 'Please enter email and password')
            return
        self.api.login(email, password, self.on_login_response)
    
    def on_login_response(self, response, error=None):
        if error:
            self.show_popup('Error', 'Connection failed')
            return
        if response and response.status_code == 200:
            data = response.json()
            self.api.save_token(data['token'])
            self.root.current = 'dashboard'
        else:
            self.show_popup('Error', 'Invalid credentials')
    
    def register(self, email, password, name, phone):
        if not all([email, password, name, phone]):
            self.show_popup('Error', 'Please fill all fields')
            return
        self.api.register(email, password, name, phone, self.on_register_response)
    
    def on_register_response(self, response, error=None):
        if error:
            self.show_popup('Error', 'Connection failed')
            return
        if response and response.status_code == 201:
            data = response.json()
            self.api.save_token(data['token'])
            self.root.current = 'dashboard'
        elif response and response.status_code == 409:
            self.show_popup('Error', 'Email already registered')
        else:
            self.show_popup('Error', 'Registration failed')

if __name__ == '__main__':
    BillsReminderApp().run()
