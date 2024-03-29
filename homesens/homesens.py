#!/usr/bin/env python3

#
# Copyright (c) 2024 Juraj Lutter <juraj@lutter.sk>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

#
# Application for displaying sensors on my home network.
#
# Tested with DHT22 on FreeBSD running on an RPi 4 and
# with uRadMonitor API.
#

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

import datetime
import getopt
import os
import re
import requests
import signal
import socket
import subprocess
import sys
from urllib.parse import urlparse

from freebsd_sysctl import Sysctl

class HomeSensorsApp(Gtk.Window):
    # Sensor number, default 0
    sensnum = 0

    # dict:
    # sensornumber: [{prop1: val1}, {prop2: val2}, ...]
    sensors = {}

    # Flags
    lflag = False
    Uflag = True
    Tflag = "temperature"
    Hflag = "humidity"

    # uRadMonitor in question
    uradmon_id = None
    uradmon_userid = None
    uradmon_userkey = None
    uradmon_api = "https://data.uradmonitor.com/api/v1/devices"

    """
    Fetch JSON from uRadMonitor API
    """
    def fetch_uradmon_data(self):
        try:
            # Make an HTTP GET request to the URL
            response = requests.get(self.uradmon_api,
                    headers={"X-User-Id": self.uradmon_userid,
                        "X-User-Hash": self.uradmon_userkey})
            
            # Raise an exception if the request was unsuccessful
            response.raise_for_status()
            
            # Parse the response as JSON
            data = response.json()
            
            return data
        except requests.RequestException as e:
            sys.stderr.write("Error fetching data from {}: {}\n".format(self.uradmon_api, e))
            return None

    def __init__(self):
        super().__init__()

        if (not self.parse_args() or not self.check_args()):
            raise SyntaxError()

        self.h_delete_event = self.connect("delete-event", Gtk.main_quit)
        self.h_window_state_event = self.connect("window-state-event", self.on_window_state_event)
        self.h_key_press_event = self.connect("key-press-event", self.on_key_press)
        self.connect("realize", self.on_realize)

        # setup vars
        self.isfullscreen = False
        self.isdone = False
        self.inverted = False

        # initial values (values not read)
        self.temperature = None
        self.humidity = None
        self.cpm = None

        self.set_title("Domace senzory")
        self.set_name("domace-senzory-app");

        self.fullscreen()

        # Box for auxiliary items
        vbox_aux = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Box for values
        vbox_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Heading1 at the top
        self.mainlabel = Gtk.Label(label=None)
        self.mainlabel_css = self.mainlabel.get_style_context()
        self.mainlabel_css.add_class("main-label-normal")
        vbox_main.pack_start(self.mainlabel, False, True, 0)

        # Frame for Heading2 and Value1
        # frame_h2_v1 = Gtk.Frame()
        # vbox_main.pack_start(frame_h2_v1, True, False, 0)

        vbox_h2_v1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox_h2_v1.set_halign(Gtk.Align.CENTER)
        vbox_h2_v1.set_valign(Gtk.Align.START)
        # frame_h2_v1.add(vbox_h2_v1)
        vbox_main.pack_start(vbox_h2_v1, False, True, 0)

        dtbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing = 36)
        dtbox.set_halign(Gtk.Align.CENTER)
        # dtbox.get_style_context().add_class("border2px")
        vbox_h2_v1.pack_start(dtbox, True, False, 0)

        self.clockdate = Gtk.Label(label="Initializing...")
        self.clockdate.get_style_context().add_class("clock")
        self.clockdate.set_halign(Gtk.Align.START)
        dtbox.pack_start(self.clockdate, True, False, 0)

        self.clocktime = Gtk.Label(label="Initializing...")
        self.clocktime.get_style_context().add_class("clock")
        self.clocktime.set_halign(Gtk.Align.CENTER)
        dtbox.pack_start(self.clocktime, True, False, 0)

        # Spacer to push content to the bottom
        spacer = Gtk.Box()
        vbox_main.pack_start(spacer, True, True, 0)

        # Horizontal box for frames in the middle
        hbox_middle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox_main.pack_start(hbox_middle, False, True, 0)

        # Horizontal box for frames at the bottom
        hbox_bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox_main.pack_start(hbox_bottom, False, True, 0)

        if (self.Uflag is True):
            # Frames for CPM and Radiation
            frame = Gtk.Frame()
            frame.set_label(None)
            frame.get_style_context().add_class("bottom-frame")

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            frame.add(vbox)

            radlabel = Gtk.Label(label="Radiácia [µSv]")
            radlabel.get_style_context().add_class("radlabel")
            vbox.pack_start(radlabel, False, False, 0)

            self.radvalue = Gtk.Label(label="")
            self.radvalue_css = self.radvalue.get_style_context()
            self.radvalue_css.add_class("radvalue")
            vbox.pack_start(self.radvalue, False, False, 0)

            hbox_middle.pack_start(frame, True, True, 0)

            frame = Gtk.Frame()
            frame.set_label(None)
            frame.get_style_context().add_class("bottom-frame")

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            frame.add(vbox)

            cpmlabel = Gtk.Label(label="CP/M")
            cpmlabel.get_style_context().add_class("cpmlabel")
            vbox.pack_start(cpmlabel, False, False, 0)

            self.cpmvalue = Gtk.Label(label="")
            self.cpmvalue_css = self.cpmvalue.get_style_context()
            self.cpmvalue_css.add_class("cpmvalue")
            vbox.pack_start(self.cpmvalue, False, False, 0)

            hbox_middle.pack_start(frame, True, True, 0)
        else:
            self.mainlabel.set_text("uRadMonitor disabled")

        # Frames for Heading3/Value2 and Heading4/Value3
        frame = Gtk.Frame()
        frame.set_label(None)
        frame.get_style_context().add_class("bottom-frame")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        frame.add(vbox)

        templabel = Gtk.Label(label="Teplota [℃]")
        templabel.get_style_context().add_class("templabel")
        vbox.pack_start(templabel, False, False, 0)

        self.tempvalue = Gtk.Label(label="")
        self.tempvalue_css = self.tempvalue.get_style_context()
        self.tempvalue_css.add_class("tempvalue")
        vbox.pack_start(self.tempvalue, False, False, 0)

        hbox_bottom.pack_start(frame, True, True, 0)

        frame = Gtk.Frame()
        frame.set_label(None)
        frame.get_style_context().add_class("bottom-frame")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        frame.add(vbox)

        humlabel = Gtk.Label(label="Vlhkosť [%]")
        humlabel.get_style_context().add_class("humlabel")
        vbox.pack_start(humlabel, False, False, 0)

        self.humvalue = Gtk.Label(label="")
        self.humvalue_css = self.humvalue.get_style_context()
        self.humvalue_css.add_class("humvalue")
        vbox.pack_start(self.humvalue, False, False, 0)

        hbox_bottom.pack_start(frame, True, True, 0)

        self.add(vbox_main)

        self.apply_css()

        # Fire a timer every 1s
        GLib.timeout_add_seconds(1, self.do_update_date_time)
        # Fire a timer every 5 seconds
        GLib.timeout_add_seconds(5, self.do_update_values)

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css = b"""
        * {
            background-color: #000;
            color: #FFF;
        }
        .main-label-normal {
            font: 36px "Seven Segment";
            color: #ccd684;
        }
        .main-label-inverted {
            font: 36px "Seven Segment";
            background-color: #ccd684;
            color: #000000;
        }
        .border2px {
            font-size: 36px;
            border-width: 2px;
            border-color: #FFF;
        }
        .radlabel {
            background-color: #5b3f0f;
            color: #FFFF00;
            font-size: 36px;
        }
        .radvalue {
            background-color: #3f033d;
            color: #FFFF00;
            font: 80px "The Led Display St";
        }
        .cpmlabel {
            background-color: #e8b7c3;
            color: #231cef;
            font-size: 36px;
        }
        .cpmvalue {
            background-color: #21040b;
            color: #c3e8b7;
            font: 80px "The Led Display St";
        }
        .templabel {
            background-color: #008000;
            color: #FFFF00;
            font-size: 36px;
        }
        .tempvalue {
            background-color: #032607;
            color: #FFFF00;
            font: 80px "The Led Display St";
        }
        .humlabel {
            background-color: #0000FF;
            color: #FFFFFF; 
            font-size: 36px;
        }
        .humvalue {
            background-color: #10083a;
            color: #FFFFFF;
            font: 80px "The Led Display St";
        }
        .clock {
            font: 42px "DS-Digital";
            border-width: 1px;
            border-color: #000;
        }
        .bottom-frame {
            border-width: 2px;
            border-color: #FFF;
        }
        .value-error {
            color: #6b4a4a;
            font: 80px "The Led Display St";
        }
        """
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_realize(self, widget):
        self.get_window().set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), 'none'))
        self.do_update_date_time()
        self.do_update_values()
        return True

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:  # Requires from gi.repository import Gdk
            if self.isfullscreen:
                self.unfullscreen()
                self.gdk_window.set_cursor(self.old_cursor)
            else:
                self.fullscreen()
                self.gdk_window.set_cursor(self.hidden_cursor)
        return True

    def on_window_state_event(self, widget, event):
        self.isfullscreen = bool(Gdk.WindowState.FULLSCREEN & event.new_window_state)
        return True

    def on_draw(self, widget, cr):
        Gdk.cairo_set_source_rgba(cr, Gdk.RGBA(0, 0, 0, 1)) 
        cr.paint()
        return True

    """
    def do_update_mainlabel(self):
        if self.inverted is False:
            self.inverted = True
            self.mainlabel_css.add_class("main-label-inverted")
            self.mainlabel_css.remove_class("main-label-normal")
        else:
            self.inverted = False
            self.mainlabel_css.add_class("main-label-normal")
            self.mainlabel_css.remove_class("main-label-inverted")
        return True
    """

    def do_update_date_time(self):
        ltime = GLib.DateTime.new_now_local()
        self.clockdate.set_text("{}".format(ltime.format("%d.%m.%Y")))
        self.clocktime.set_text("{}".format(ltime.format("%H:%M:%S")))
        return True

    def do_update_values(self):
        """ Read temperature and humidity values and check for None (which means an error) """
        """ Temperature is returned in decikelvins """
        newtemperature = Sysctl("dev.gpioths.{}.{}".format(self.sensnum, self.Tflag)).value
        newhumidity = Sysctl("dev.gpioths.{}.{}".format(self.sensnum, self.Hflag)).value

        if newtemperature is None:
            self.tempvalue_css.add_class("value-error")
        else:
            """ Adjust for K to C. DHT sensors returns temperature in decikelvins """
            newtemperature -= 2731
            newtemperature /= 10

            self.tempvalue_css.remove_class("value-error")
            if (newtemperature != self.temperature):
                # update temperature
                self.tempvalue.set_text("{}".format(newtemperature))
                self.temperature = newtemperature

        if newhumidity is None:
            self.humvalue_css.add_class("value-error")
        else:
            self.humvalue_css.remove_class("value-error")
            if (newhumidity != self.humidity):
                # update humidity
                self.humvalue.set_text("{}".format(newhumidity))
                self.humidity = newhumidity

        if (self.Uflag is True):
            newurad = self.fetch_uradmon_data()
            if newurad is None:
                self.radvalue_css.add_class("value-error")
                self.cpmvalue_css.add_class("value-error")
            else:
                self.radvalue_css.remove_class("value-error")
                self.cpmvalue_css.remove_class("value-error")
                umstatus = None
                umcpm = None
                for item in newurad:
                    if (item["id"] == self.uradmon_id):
                        umstatus = item["status"]
                        umcpm = item["avg_cpm"]
                        umfactor = item["factor"]
                        umvoltage = item["avg_voltage"]
                        umduty = item["avg_duty"]
                if ((umstatus is not None) and (umstatus == "1") and
                        (umcpm is not None)):
                    if (self.cpm != umcpm):
                        self.cpm = umcpm
                        self.rad = (float(umcpm) * float(umfactor))
                        self.cpmvalue.set_text("%3u" % int(self.cpm))
                        self.radvalue.set_text("%1.2f" % self.rad)
                    self.mainlabel.set_text("Ugmt: %3.2fV, Duty: %3.2f%%" % (float(umvoltage), float(umduty) / 10))

        return True


    def usage(self):
        sys.stderr.write("%s [arguments]\n"
                "\n"
                "Valid arguments are: [-h|--help] [-l|--list|--list-sensors] "
                "[-s <n>|--sensor=<n>] [-T <leafoid>] [-H <leafoid>] "
                "<[-U|--no-uradmon] | "
                "--uradmon-id=<id> --uradmon-userid=<userid> --uradmon-userkey=<userkey>>\n"
                "\n"
                "-h|--help                      Show this help\n"
                "-l|--list|--list-sensors       List sensors detected\n"
                "-s <n>|--sensor=<n>            Use sensor number \"n\" (default: 0)\n"
                "-T <leafoid>                   Use leafoid for temperature reading (default: temperature)\n"
                "-H <leafoid>                   Use leafoid for humidity reading (default: humidity)\n"
                "\n"
                "-U|--no-uradmon                Do not query and display uRadMonitor data\n"
                "\n"
                "If -U or --no-urandom is NOT specified, then the following arguments are MANDATORY:\n"
                "\n"
                "--uradmon-id=<id>              Specify uRadMon Device ID\n"
                "--uradmon-userid=<userid>      Specify uRadMon User ID\n"
                "--uradmon-userkey=<userkey>    Specify uRadMon User Auth Key\n"
                "--uradmon-api=<apiurl>         Specity uRadMon API URL, default:\n"
                "                               https://data.uradmonitor.com/api/v1/devices\n"
                "\n" % (os.path.basename(sys.argv[0])))

    def detect_sensors(self):
        thsbase = "dev.gpioths"
        thsens = Sysctl(thsbase).children
        if thsens is None:
            return False
        basere = re.compile(r"^{}\.([0-9]+)\.%(\S+)$".format(thsbase))
        for sens in thsens:
            result = basere.match(sens.name)
            if result is None:
                continue
            _snum = result[1]
            _sprop = result[2]
            _svalue = sens.value
            _skey = str(_snum)
            if (_skey not in self.sensors.keys()):
                self.sensors[_skey] = {}
            self.sensors[_skey][_sprop] = _svalue
        if (len(self.sensors) < 1):
            return False

        return True

    def list_sensors(self):
        if (len(self.sensors) > 0):
            print("ID  Driver       Description")
            for sens in self.sensors.items():
                print("%-2s  %-12s %s" % (sens[0], sens[1]["driver"], sens[1]["desc"]))
        return

    def check_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def check_valid_arg(self, arg):
        argpattern = r"^[0-9a-zA-Z\-_]+$"
        return re.match(argpattern, arg)

    def is_hostname_resolvable(self, url):
        try:
            hostname = requests.utils.urlparse(url).hostname
            socket.gethostbyname(hostname)
            return True
        except socket.error:
            return False

    def webserver_reachable(self, url):
        try:
            response = requests.get(url, timeout=5)
            # Check for successful status codes (2xx)
            return response.status_code // 100 == 2
        except requests.RequestException:
            return False

    def parse_args(self):
        try:
            opts, args = getopt.getopt(sys.argv[1:], "hH:ls:T:U",
                    ["help",
                        "list",
                        "list-sensors",
                        "no-uradmon",
                        "sensor=",
                        "uradmon-id=",
                        "uradmon-userid=",
                        "uradmon-userkey=",
                        "uradmon-api="])
        except getopt.GetoptError as err:
            usage()
            sys.exit(2)

        for o, a in opts:
            if o in ("-h", "--help"):
                usage()
                sys.exit(2)
            elif o in ("-l", "--list", "--list-sensors"):
                self.lflag = True
            elif o in ("-s", "--sensor"):
                try:
                    self.sensnum = int(a)
                except ValueError as ve:
                    sys.stderr.write("ERROR: Invalid sensor number, only numbers are valid.\n")
                    sys.exit(1)
            elif o == "-H":
                self.Hflag = a
            elif o == "-T":
                self.Tflag = a
            elif o in ("-U", "--no-uradmon"):
                self.Uflag = False
            elif o == "--uradmon-id":
                if self.check_valid_arg(a):
                    self.uradmon_id = a
                else:
                    sys.stderr.write("ERROR: Invalid uRadMon Device ID specified.\n")
                    sys.exit(1)
            elif o == "--uradmon-userid":
                if self.check_valid_arg(a):
                    self.uradmon_userid = a
                else:
                    sys.stderr.write("ERROR: Invalid uRadMon User ID specified.\n")
                    sys.exit(1)
            elif o == "--uradmon-userkey":
                if self.check_valid_arg(a):
                    self.uradmon_userkey = a
                else:
                    sys.stderr.write("ERROR: Invalid uRadMon User Key specified.\n")
                    sys.exit(1)
            elif o == "--uradmon-api":
                if self.check_valid_url(a):
                    self.uradmon_api = a
                else:
                    sys.stderr.write("ERROR: Invalid uRadMon API endpoint specified.\n")
                    sys.exit(1)
            else:
                usage()
                sys.exit(2)
        return True

    def check_args(self):
        if self.Uflag and (
                self.uradmon_id is None or
                self.uradmon_userid is None or
                self.uradmon_userkey is None):
            print("WARNING: uRadMonitor parameters are not specified, disabling uRadMonitor.")
            self.Uflag = False

        if self.detect_sensors() is False:
            sys.stderr.write("ERROR: No sensor(s) detected!\n")
            sys.exit(1)

        if (self.lflag is True):
            self.list_sensors()
            sys.exit(1)

        if str(self.sensnum) not in self.sensors.keys():
            sys.stderr.write("ERROR: Invalid sensor number specified!\n")
            sys.exit(1)

        if (self.Uflag is True and
                (not self.is_hostname_resolvable(self.uradmon_api) or
                    not self.webserver_reachable(self.uradmon_api))):
            self.Uflag = False
            print("WARNING: uRadMon API URL {} does not resolve and/or respond, disabling uRadMontitor.".format(self.uradmon_api))

        return True

""" Catch keyboard interrupt """
def sigint_handler(signum, frame):
    print("Exiting...")
    sys.exit(1)

if __name__ == '__main__':
    try:
        signal.signal(signal.SIGINT, sigint_handler)
        app = HomeSensorsApp()
        app.show_all()
        Gtk.main()
    except Exception as e:
        sys.stderr.write(f"ERROR: Exception in main: {e}\n")
        Gtk.main_quit()

