#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 PAL Robotics SL.
# Released under the BSD License.
#
# Authors:
#   * Siegfried-A. Gevatter

import curses
import math

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg._Char import Char

class Velocity(object):

    def __init__(self, min_velocity, max_velocity, num_steps):
        assert min_velocity > 0 and max_velocity > 0 and num_steps > 0
        self._min = min_velocity
        self._max = max_velocity
        self._num_steps = num_steps
        if self._num_steps > 1:
            self._step_incr = (max_velocity - min_velocity) / (self._num_steps - 1)
        else:
            # If num_steps is one, we always use the minimum velocity.
            self._step_incr = 0

    def __call__(self, value, step):
        """
        Takes a value in the range [0, 1] and the step and returns the
        velocity (usually m/s or rad/s).
        """
        if step == 0:
            return 0

        assert step > 0 and step <= self._num_steps
        max_value = self._min + self._step_incr * (step - 1)
        return value * max_value

class TextWindow():

    _screen = None
    _window = None
    _num_lines = None

    def __init__(self, stdscr, lines=10):
        self._screen = stdscr
        self._screen.nodelay(True)
        curses.curs_set(0)

        self._num_lines = lines

    def read_key(self):
        keycode = self._screen.getch()
        return keycode if keycode != -1 else None

    def clear(self):
        self._screen.clear()

    def write_line(self, lineno, message):
        if lineno < 0 or lineno >= self._num_lines:
            raise ValueError, 'lineno out of bounds'
        height, width = self._screen.getmaxyx()
        y = (height / self._num_lines) * lineno
        x = 10
        for text in message.split('\n'):
            text = text.ljust(width)
            self._screen.addstr(y, x, text)
            y += 1

    def refresh(self):
        self._screen.refresh()

    def beep(self):
        curses.flash()

class KeyTeleop():

    _interface = None

    _linear = None
    _angular = None


    def __init__(self, interface):
        self._interface = interface
        self._pub_cmd = rospy.Publisher('key_vel', Twist)
        self._pub_key_cmd = rospy.Publisher('key_cmd', Char)

        self._hz = rospy.get_param('~hz', 10)

        self._num_steps = rospy.get_param('~turbo/steps', 4)

        self._cmd_char = -1
        self._cmd_last_char = -1

	self.max_speed = 10

    def run(self):
        self._linear = 0
        self._angular = 0

        rate = rospy.Rate(self._hz)
        self._running = True
        while self._running:
            keycode = self._interface.read_key()
            if keycode:
                if self._key_pressed(keycode):
                    self._publish()
            else:
                self._publish()
                rate.sleep()

    def _get_twist(self, linear, angular):
        twist = Twist()
#        if linear >= 0:
#            twist.linear.y = self._forward(1.0, linear)
#        else:
#            twist.linear.y = self._backward(-1.0, -linear)
#        twist.angular.z = self._rotation(math.copysign(1, angular), abs(angular))
	twist.linear.y = linear
	twist.angular.z = angular
        return twist

    def _key_pressed(self, keycode):
        movement_bindings = {
            curses.KEY_UP:    ( 1,  0),
            curses.KEY_DOWN:  (-1,  0),
            curses.KEY_LEFT:  ( 0,  1),
            curses.KEY_RIGHT: ( 0, -1),
        }
        speed_bindings = {
            ord(' '): (0, 0),
        }
        if keycode in movement_bindings:
            acc = movement_bindings[keycode]
            ok = False
            if acc[0]:
                linear = self._linear + acc[0]
#                if abs(linear) <= self._num_steps:
#                    self._linear = linear
#                    ok = True
		if( abs(linear)<=self.max_speed ):
			self._linear = linear
			self._angular = 0
			ok = True
            if acc[1]:
                angular = self._angular + acc[1]
#                if abs(angular) <= self._num_steps:
#                    self._angular = angular
#                    ok = True
		if( abs(angular)<=self.max_speed ):
			self._angular = angular
			self._linear = 0
			ok = True
            if not ok:
                self._interface.beep()
        elif keycode in speed_bindings:
            acc = speed_bindings[keycode]
            # Note: bounds aren't enforced here!
            if acc[0] is not None:
                self._linear = acc[0]
            if acc[1] is not None:
                self._angular = acc[1]
        elif keycode == ord('q'):
            self._running = False
            rospy.signal_shutdown('Bye')
        elif keycode >= ord('a') and keycode <= ord('z'):
            self._cmd_char = keycode
        else:
            return False

        return True

    def _publish(self):
        self._interface.clear()
        self._interface.write_line(2, 'Linear: %d, Angular: %d' % (self._linear, self._angular))
        self._interface.write_line(5, 'Use arrow keys to move, space to stop, q to exit.')
        if self._cmd_char!=-1:
            self._cmd_last_char = self._cmd_char
        if self._cmd_last_char!=-1:
            self._interface.write_line(7, 'Last input command %c' % (self._cmd_last_char))
        else:
            self._interface.write_line(7, 'Have no input yet')
        self._interface.refresh()

        twist = self._get_twist(self._linear, self._angular)
        self._pub_cmd.publish(twist)

        if self._cmd_char!=-1:
            c = Char()
            c.data = self._cmd_char
            self._pub_key_cmd.publish(c)
            self._cmd_char = -1


def main(stdscr):
    rospy.init_node('key_teleop')
    #app = SimpleKeyTeleop(TextWindow(stdscr))
    app = KeyTeleop(TextWindow(stdscr))
    app.run()

if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except rospy.ROSInterruptException:
        pass
