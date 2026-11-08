# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0


from Plugins.Plugin import PluginDescriptor
from .Debug import logger
from .Version import PLUGIN, VERSION
from .JobCockpit import JobCockpit
from .PluginUtils import WHERE_JOBCOCKPIT
from . import _
from .JobSupervisor import JobSupervisor
from .SkinUtils import loadPluginSkin
from .PyReplace import sync as syncPYs


loadPluginSkin(PLUGIN)

LEGACY_MARKERS = ("getSuccessfulJobs",)  # in the Task of earlier versions of the plugin, not in the one of enigma2 (see PyReplace)


def main(session, plugin_id="", **__kwargs):
    logger.info("plugin_id: %s", plugin_id)
    session.open(JobCockpit, plugin_id)


def autoStart(reason, **kwargs):
    if reason == 0:  # startup
        if "session" in kwargs:
            logger.info("+++ Version: %s starts...", VERSION)
            JobSupervisor.getInstance()
            # an update of enigma2 has replaced Components/Task: the plugin's one is put back (and the new original saved). e2 has imported the
            # new one already, ours is used from the next start on.
            syncPYs(LEGACY_MARKERS)
    elif reason == 1:  # shutdown
        logger.info("--- shutdown")


def Plugins(**__kwargs):
    descriptors = [
        PluginDescriptor(
            where=[
                PluginDescriptor.WHERE_AUTOSTART,
                PluginDescriptor.WHERE_SESSIONSTART
            ],
            fnc=autoStart,
            needsRestart=True
        ),
        PluginDescriptor(
            name="JobCockpit",
            where=[
                PluginDescriptor.WHERE_PLUGINMENU,
                PluginDescriptor.WHERE_EXTENSIONSMENU
            ],
            icon="plugin.png",
            description=_("Manage Jobs"),
            fnc=main,
            needsRestart=True
        ),
        PluginDescriptor(
            name=_("Jobs"),
            description=_("Manage Jobs"),
            where=WHERE_JOBCOCKPIT,
            fnc=main,
            needsRestart=True
        ),
    ]
    try:
        descriptors += [
            PluginDescriptor(
                where=PluginDescriptor.WHERE_SKINCHANGE,
                fnc=loadPluginSkin
            )
        ]
    except Exception:
        pass

    return descriptors
