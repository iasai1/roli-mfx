from __future__ import absolute_import, print_function, unicode_literals
from functools import partial
import sys
from ableton.v3.control_surface.elements import EncoderElement
from ableton.v3.control_surface import MIDI_CC_TYPE
from ableton.v3.control_surface import ControlSurface, ControlSurfaceSpecification
from ableton.v3.control_surface.capabilities import CONTROLLER_ID_KEY, HIDDEN, NOTES_CC, PORTS_KEY, SCRIPT, SYNC, controller_id, inport, outport
from ableton.v3.control_surface.elements_base import ElementsBase, create_matrix_identifiers
from ableton.v3.live.util import song
import Live


def get_capabilities():
    return {
            CONTROLLER_ID_KEY: controller_id(vendor_id=2536,
                                             product_ids=[81],
                                             model_name=['Roli Lightblock']),
            PORTS_KEY: [inport(props=[NOTES_CC, SCRIPT, HIDDEN]),
                        outport(props=[NOTES_CC, SCRIPT, HIDDEN]),
                        outport(props=[SYNC])]}


def create_instance(c_instance):
    return RoliMFX(c_instance=c_instance)


class Elements(ElementsBase):

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        add_button_matrix = partial(self.add_button_matrix,
                                    msg_type=MIDI_CC_TYPE)
        add_button_matrix(create_matrix_identifiers(112, 120), 'mfxbuttons')
        add_encoder_matrix = partial(self.add_encoder_matrix,
                                     msg_type=MIDI_CC_TYPE)
        add_encoder_matrix(create_matrix_identifiers(102, 106), 'mfxfaders')


class Specification(ControlSurfaceSpecification):
    elements_type = Elements
    identity_response_id_bytes = (71, 83, 0, 25)


class RoliMFX(ControlSurface):

    def __init__(self, *a, **k):
        (super().__init__)(Specification, *a, **k)

    def _create_components(self):
        self._mfxbuttons = getattr(self.elements, 'mfxbuttons_raw', None)
        if self._mfxbuttons:
            self._initialize_buttons()
        self._mfxfaders = getattr(self.elements, 'mfxfaders_raw', None)

    def disconnect(self):
        super().disconnect()

    def setup(self):
        super().setup()
        with self.component_guard():
            self._create_components()

    def _initialize_buttons(self):
        for button in self._mfxbuttons:
            if button:
                button.add_value_listener(lambda value, b=button: self._on_mfxpad_pressed(value, b))

    def _on_mfxpad_pressed(self, value, button):
        # make sure we are bounded to a channel with an audio effect rack with a special preset
        cur_track = song().view.selected_track
        mfx_device = None
        for device in cur_track.devices:
            if isinstance(device, Live.Device.Device) and device.class_name == 'AudioEffectGroupDevice' and device.name == "MFX_VOX":
                mfx_device = device
        if mfx_device is None:
            return
        devices_in_chain = mfx_device.chains[0].devices
        if len(devices_in_chain) > 0:
            Live.Application.get_application().view.show_view('Detail/DeviceChain')
            Live.Application.get_application().view.focus_view('Detail/DeviceChain')
            new_index = button.message_identifier() % 112 # min msg id is 112 - hence counting from 112 on
            song().view.select_device(devices_in_chain[new_index])
            self._map_faders_to_macros(devices_in_chain[new_index])

    def _map_faders_to_macros(self, device):
        # Map the faders to the selected device's macros
        if hasattr(device, 'parameters') and len(device.parameters) > 1:
            macros = device.parameters[1:9]
            for i, fader in enumerate(self._mfxfaders[:min(4, len(macros))]):
                macro = macros[i]
                if fader and isinstance(fader, EncoderElement):
                    fader.connect_to(macro)