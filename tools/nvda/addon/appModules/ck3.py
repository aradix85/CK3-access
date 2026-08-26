# Sleep mode for Crusader Kings III with the ck3_access layer.
#
# The reader speaks for itself through the NVDA controller client, so NVDA's own
# reporting is duplication and its keys are keys the game cannot have. Sleep mode
# leaves the controller client working: NVDA's speak handler only returns early
# for SLEEP_FULL, which ordinary sleep mode does not set.
#
# No executable mapping is needed here. An app module is named after the
# executable, and `ck3` is already a legal Python module name - unlike
# `cataclysm-bn-tiles` in the Bright Nights add-on this is modelled on, which
# needs a global plugin to register the name.

import appModuleHandler


class AppModule(appModuleHandler.AppModule):
    sleepMode = True
