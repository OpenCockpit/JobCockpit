# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0


from enigma import eTimer
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Sources.List import List
from Components.Task import Job
from .__init__ import _
from .Debug import logger
from .JobSupervisor import JobSupervisor


class JobCockpit(Screen):

    NOT_STARTED, IN_PROGRESS, FINISHED, FAILED = range(4)

    def __init__(self, session, plugin_id=""):
        logger.info("...")
        self.plugin_id = plugin_id
        self.job_supervisor = JobSupervisor.getInstance()
        Screen.__init__(self, session)
        self.skinName = "JobCockpit"
        self.setTitle(_("Job Management"))
        self['actions'] = ActionMap(
            ['JOC_Actions'],
            {
                'ok': self.exit,
                'cancel': self.exit,
                'red': self.execRed,
                'green': self.execGreen,
                'yellow': self.execYellow,
                'blue': self.execBlue
            }
        )
        self['key_red'] = Button(_('Abort current job'))
        self['key_green'] = Button(_('Abort all jobs'))
        self['key_yellow'] = Button(_('Abort all pending jobs'))
        self['key_blue'] = Button(_('Cleanup jobs'))
        self['list'] = List()
        self.update_timer = eTimer()
        self.update_timer.callback.append(self.updateList)
        self.status_text = {self.NOT_STARTED: _("Waiting"), self.IN_PROGRESS: _("In Progress"), self.FINISHED: _("Finished"), self.FAILED: _("Failed")}

        self.updateList()

    def updateList(self):
        logger.info("...")
        self.update_timer.stop()
        index = self['list'].index
        alist = []
        # alist.append(("Job", "in flight", 35, "35%", None, "MVC"))

        for plugin, job in self.job_supervisor.getPendingJobs(self.plugin_id, as_tuples=True):
            alist.append((job.name, self.status_text[job.status], job.getProgress(), f"{job.getProgress()}%", job, plugin))
        for plugin, job in self.job_supervisor.getFailedJobs(self.plugin_id, as_tuples=True):
            alist.append((job.name, self.status_text[job.status], job.getProgress(), f"{job.getProgress()}%", job, plugin))
        for plugin, job in self.job_supervisor.getSuccessfulJobs(self.plugin_id, as_tuples=True):
            alist.append((job.name, self.status_text[job.status], job.getProgress(), f"{job.getProgress()}%", job, plugin))
        self['list'].setList(alist)
        self['list'].setIndex(index)
        self.update_timer.startLongTimer(1)

    @staticmethod
    def abortJob(job, plugin_id, force=True):
        logger.info("force: %s", force)
        if job.status == Job.IN_PROGRESS:
            JobSupervisor.getInstance().getJobManager(plugin_id).AbortJob(job, force)

    def execYellow(self):
        logger.info("...")
        self.update_timer.stop()
        for entry in self["list"].list:
            _name, _status, _progress, _info, job, plugin_id = entry
            if job.status == Job.NOT_STARTED:
                self.job_supervisor.getJobManager(plugin_id).RemoveJob(job)
        self.updateList()

    def execGreen(self):
        logger.info("...")
        self.update_timer.stop()
        for entry in self["list"].list:
            _name, _status, _progress, _info, job, plugin_id = entry
            self.job_supervisor.getJobManager(plugin_id).AbortJob(job)
        self.updateList()

    def execRed(self):
        logger.info("...")
        self.update_timer.stop()
        entry = self["list"].getCurrent()
        if entry:
            _name, _status, _progress, _info, job, plugin_id = entry
            if job.status == Job.IN_PROGRESS:
                self.job_supervisor.getJobManager(plugin_id).AbortJob(job)
            else:
                self.job_supervisor.getJobManager(plugin_id).RemoveJob(job)
        self.updateList()

    def execBlue(self):
        logger.info("...")
        self.update_timer.stop()
        for job_manager in self.job_supervisor.getJobManagers().values():
            job_manager.CleanupJobs()
        self.updateList()

    def exit(self):
        self.update_timer.stop()
        self.close()
