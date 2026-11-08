# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0


from Components.Task import job_manager, JobManager
from .Debug import logger


instance = None


class JobSupervisor():

    def __init__(self):
        self.job_managers = {}
        self.job_managers["DEFAULT"] = job_manager

    @staticmethod
    def getInstance():
        global instance  # pylint: disable=global-statement
        if instance is None:
            instance = JobSupervisor()
        return instance

    def getJobManager(self, plugin_id):
        logger.info("plugin_id: %s", plugin_id)
        if plugin_id not in self.job_managers:
            self.job_managers[plugin_id] = JobManager()
        return self.job_managers[plugin_id]

    def createJobTuples(self, plugin_id, jobs, as_tuples):
        if as_tuples:
            return [(plugin_id, job) for job in jobs]
        return jobs

    def getJobManagers(self, plugin_id=""):
        if plugin_id:
            manager = self.job_managers.get(plugin_id)
            return {plugin_id: manager} if manager is not None else {}
        return self.job_managers

    def getPendingJobs(self, plugin_id="", as_tuples=False):
        jobs = []
        for plugin, manager in self.getJobManagers(plugin_id).items():
            jobs += self.createJobTuples(plugin,
                                         manager.getPendingJobs(), as_tuples)
        return jobs

    def getFailedJobs(self, plugin_id="", as_tuples=False):
        jobs = []
        for plugin, manager in self.getJobManagers(plugin_id).items():
            jobs += self.createJobTuples(plugin,
                                         manager.getFailedJobs(), as_tuples)
        return jobs

    def getSuccessfulJobs(self, plugin_id="", as_tuples=False):
        jobs = []
        for plugin, manager in self.getJobManagers(plugin_id).items():
            jobs += self.createJobTuples(plugin,
                                         manager.getSuccessfulJobs(), as_tuples)
        return jobs
