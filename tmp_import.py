import importlib
m = importlib.import_module('streamer')
print('imported streamer, Streamer has _get_target_fps:', hasattr(m.Streamer, '_get_target_fps'))
print('Streamer.set_low_quality callable:', callable(getattr(m.Streamer, 'set_low_quality', None)))
