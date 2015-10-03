from .base import MDP
from ale_python_interface import ale_lib, ALEInterface, ALEState
from itertools import imap
import numpy as np
import operator
import sys
from misc.console import type_hint
from contextlib import contextmanager


def sequence_equal(s1, s2):
    return len(s1) == len(s2) and all(imap(np.array_equal, s1, s2))


class AtariMDP(MDP):

    @type_hint('rom_path', str)
    def __init__(
            self, rom_path, obs_type='ram', stop_per_life=True,
            cutoff_frame=18000, default_frame_skip=4):
        ale_lib.setLoggerLevelError()
        self._rom_path = rom_path
        self._obs_type = obs_type
        ale = self._new_ale()
        self._action_set = [ale.getMinimalActionSet()]
        self._obs_shape = self.to_obs(ale).shape
        self._stop_per_life = stop_per_life
        self._ales = []
        self._states = []
        self._life_counts = []
        self._cutoff_frame = cutoff_frame
        self._default_frame_skip = default_frame_skip

    def _new_ale(self):
        ale = ALEInterface()
        ale.loadROM(self._rom_path)
        return ale

    # s1, s2 should both be a list of ALEState

    def _reset_ales(self, states):
        # only do the reset if we actually need it
        if not sequence_equal(self._states, states):
            self._ales = [self._new_ale() for _ in range(len(states))]
            for ale, state in zip(self._ales, states):
                ale.load_serialized(state)
            self._states = states

    def to_obs(self, ale):
        if self._obs_type == 'image':
            return self.to_rgb(ale)
        elif self._obs_type == 'ram':
            return self.to_ram(ale)
        else:
            return None

    def step_single(self, state, action, repeat=None):
        next_states, obs, rewards, dones, effective_steps = \
            self.step([state], map(lambda x: [x], action), repeat)
        return next_states[0], obs[0], rewards[0], dones[0], effective_steps[0]

    def step(self, states, action_indices, repeat=None):
        # if the current states do not match the given argument, we need to
        # reset ale to these states
        repeat = repeat or self._default_frame_skip
        self._reset_ales(states)
        next_states = []
        obs = []
        rewards = []
        dones = []
        steps = []
        for ale, action_idx in zip(self._ales, action_indices[0]):
            reward = 0
            prev_lives = ale.lives()
            per_steps = 0
            done = False
            for _ in xrange(repeat):
                reward += ale.act(self.action_set[0][action_idx])
                per_steps += 1
                if ale.game_over() or ale.getEpisodeFrameNumber() >= \
                        self._cutoff_frame:
                    done = True
                    ale.reset_game()
                    break
                elif self._stop_per_life and ale.lives() != prev_lives:
                    done = True
                    break
            next_state = ale.get_serialized()
            next_states.append(next_state)
            obs.append(self.to_obs(ale))
            rewards.append(reward)
            dones.append(done)
            steps.append(per_steps)
        self._states = next_states[:]
        return next_states, obs, rewards, dones, steps

    @property
    def support_repeat(self):
        return True

    # return: (states, observations)
    def sample_initial_states(self, n):
        self._ales = [self._new_ale() for _ in xrange(n)]
        self._states = map(lambda x: x.get_serialized(), self._ales)
        obs = map(self.to_obs, self._ales)
        return self._states[:], obs

    @property
    def action_set(self):
        return self._action_set

    @property
    def action_dims(self):
        return [len(self._action_set[0])]

    @property
    def observation_shape(self):
        return self._obs_shape

    def to_rgb(self, ale):
        (screen_width, screen_height) = ale.getScreenDims()
        arr = np.zeros((screen_height, screen_width, 4), dtype=np.uint8)
        ale.getScreenRGB(arr)
        # The returned values are in 32-bit chunks. How to unpack them into
        # 8-bit values depend on the endianness of the system
        if sys.byteorder == 'little':  # the layout is BGRA
            arr = arr[:, :, 2::-1]  # (0, 1, 2) <- (2, 1, 0)
        # the layout is ARGB (I actually did not test this.
        # Need to verify on a big-endian machine)
        else:
            arr = arr[:, :, 1:]
        return arr

    def to_ram(self, ale):
        ram_size = ale.getRAMSize()
        ram = np.zeros((ram_size), dtype=np.uint8)
        ale.getRAM(ram)
        MAX_RAM = 255
        ram = (np.array(ram) * 1.0 / MAX_RAM) * 2 - 1
        return ram
