import sys

SIM_CYCLES = 1e3


#Numbers from: https://arxiv.org/pdf/2105.03814.pdf#cite.gomezluna2021repo
MRAM_SIZE = 2**26

WRAM_SIZE = 2**16

MRAM_READ_ALPHA = 77
MRAM_WRITE_ALPHA = 61

HOST_TO_DPU_BW = 0.1 * (2**30)

DPU_TO_HOST_BW = 0.5 * (2**30)

DPU_CLOCK_SPEED = 350e6

JobIndex = 0


class Job:
	Priority = 0
	WorkLoadSize = 0
	WorkLoadDispatched = 0
	WorkLoadCompleted = 0

	CyclesPerByte = 0
	ID = 0

	def __init__(self, WorkLoadSize, Priority, BytesPerCycle) -> None:
		global JobIndex
		self.Priority = Priority
		self.WorkLoadSize = WorkLoadSize
		self.CyclesPerByte = BytesPerCycle
		self.ID = JobIndex

		JobIndex += 1


class Task:
	Priority = 0
	PartitionSize = 0
	CyclesPerByte = 0

	ParentJob: Job = None

	Valid = False

	Active = False
	InternalCyclesRemaining = 0

	Transfering = False
	IsToHost = False
	IsToDPU = False
	TransferCyclesRemaining = 0

	TaskID = 0

	def __init__(self, TaskID, WorkLoadSize, Priority, BytesPerCycle) -> None:
		self.TaskID = TaskID
		self.Priority = Priority
		self.WorkLoadSize = WorkLoadSize
		self.CyclesPerByte = BytesPerCycle


def getTaskLabel(task: Task) -> str:
	return str(task.ParentJob.ID) + "-" + str(task.TaskID)


class SimState:
	#	InternalDMAActive = False

	DPUActive = False
	ActiveTask: Task = None

	MemoryBusActive = False
	MemoryBusTask: Task = None

	TaskSize = 0
	TotalCycles = 0

	JobList: list[Job] = None
	TaskArray: list[Task] = None

	OutQueue: list = None
	InQueue: list = None

	Task_RR_Index = 0

	def pruneJobs(self) -> None:
		modified = True

		while modified:
			modified = False
			for job in self.JobList:
				if job.WorkLoadCompleted >= job.WorkLoadSize:
					print("--- Job : ", job.ID, " finished at cycle : ", self.TotalCycles)
					self.JobList.remove(job)
					modified = True

	def SimMemoryBus(self):
		#if outbound task waiting, start its transfer
		self.FindBusOutputJob()

		#if need to read from host
		self.FindBusInputJob()

		#if memory bus is active, continue whatever transfer is happening
		self.SimMemoryBusTransfer()

	def SimMemoryBusTransfer(self):
		#if memory bus is active, continue whatever transfer is happening
		if self.MemoryBusActive:
			self.MemoryBusTask.TransferCyclesRemaining -= SIM_CYCLES

			if self.MemoryBusTask.TransferCyclesRemaining <= 0:
				print("Done transfering", getTaskLabel(self.MemoryBusTask), "...")

				if self.MemoryBusTask.IsToHost:
					self.MemoryBusTask.ParentJob.WorkLoadCompleted += self.TaskSize
					print("Task ", self.MemoryBusTask.ParentJob.ID, " - ", self.MemoryBusTask.TaskID,  " has finished : ",
                                            self.MemoryBusTask.ParentJob.WorkLoadCompleted, '/', self.MemoryBusTask.ParentJob.WorkLoadSize)
					self.MemoryBusTask.Valid = False

					self.pruneJobs()

				self.MemoryBusTask.Transfering = False
				self.MemoryBusTask = None
				self.MemoryBusActive = False

	def FindBusInputJob(self):
		#if need to read from host
		if not self.MemoryBusActive:

			#Is there a spot available on the DPU?
			FreeTask = getFreeTask(self.TaskArray)

			if FreeTask != None and self.InQueue:
				NextJob = self.InQueue.pop(0)

				#Associate Task with Job, and mark as transfering to DPU
				FreeTask.ParentJob = NextJob
				FreeTask.CyclesPerByte = NextJob.CyclesPerByte
				FreeTask.TransferCyclesRemaining = hostToDPUTransfer(self.TaskSize)
				FreeTask.InternalCyclesRemaining = getInternalCycles(
					self.TaskSize, FreeTask.CyclesPerByte)
				FreeTask.Transfering = True
				FreeTask.Valid = True

				print("Starting transfer of job", getTaskLabel(FreeTask))

				#Let global state know memory bus is active
				self.MemoryBusActive = True
				self.MemoryBusTask = FreeTask

	def FindBusOutputJob(self):
		#if outbound task waiting, start its transfer
		if not self.MemoryBusActive and self.OutQueue:
			print("Starting transfer back to host")
			self.MemoryBusTask = self.OutQueue.pop(0)

			self.MemoryBusTask.Transfering = True
			self.MemoryBusActive = True

	def SimDPU(self):
		#if need to start a task
		sim.FindDPUTask()

		#Process currently running task
		sim.RunDPUTask()

	def FindDPUTask(self):
		#if need to start a task
		if not self.DPUActive:

			#Is there a task that needs to be run?
			NextTask: Task = self.selectTask()
			#NextTask: Task = self.selectTask_RR()

			if NextTask != None:
				print("Starting task ", NextTask.TaskID,
				      ", job ID: ", NextTask.ParentJob.ID)
				NextTask.Active = True

				self.ActiveTask = NextTask
				self.DPUActive = True

	def RunDPUTask(self):
		#Process currently running task
		if self.ActiveTask != None:
			self.ActiveTask.InternalCyclesRemaining -= SIM_CYCLES

			#If task has finished, begin transfering it back to Host
			if self.ActiveTask.InternalCyclesRemaining <= 0:
				print("Done")

				self.ActiveTask.Active = False

				self.ActiveTask.TransferCyclesRemaining = DPUToHostTransfer(self.TaskSize)
				self.ActiveTask.IsToHost = True

				#Start transfer
				if not self.MemoryBusActive:
					print("Starting transfer back to host")
					self.ActiveTask.Transfering = True

					self.MemoryBusTask = self.ActiveTask
					self.MemoryBusActive = True

				#Bus is currently busy, put task in outbound queue
				else:
					self.OutQueue.append(self.ActiveTask)

				self.DPUActive = False
				self.ActiveTask = None

	def selectTask(self) -> Task:
		global sim
		for task in self.TaskArray:
			if task.Valid and not task.Active and not task.Transfering and task.InternalCyclesRemaining > 0:
				return task

		return None

	def selectTask_RR(self) -> Task:
		task = self.TaskArray[self.Task_RR_Index]

		self.Task_RR_Index = (self.Task_RR_Index + 1) % len(self.TaskArray)

		if task.Valid and not task.Active and not task.Transfering and task.InternalCyclesRemaining > 0:
			return task

		else:
			return None

	#Fill input job queue in round robin order
	def fillInQueue_RR(self) -> None:
		self.InQueue = []

		tmpList = self.JobList.copy()

		while tmpList:
			for job in tmpList:
				if job.WorkLoadDispatched < job.WorkLoadSize:
					self.InQueue.append(job)
					job.WorkLoadDispatched += sim.TaskSize

			modified = True
			while modified:
				modified = False
				for job in tmpList:
					if job.WorkLoadDispatched >= job.WorkLoadSize:
						print("--- Job : ", job.ID, " fully queued")
						tmpList.remove(job)
						modified = True

	#Fill input job queue in FCFS order
	def fillInQueue_FCFS(self) -> None:
		self.InQueue = []

		tmpList = self.JobList.copy()

		for job in tmpList:

			while job.WorkLoadDispatched < job.WorkLoadSize:
				self.InQueue.append(job)
				job.WorkLoadDispatched += sim.TaskSize


sim = SimState()


def getFreeTask(TaskArray: list[Task]) -> Task:
	for task in TaskArray:
		if not task.Valid:
			return task

	return None


def read_mramLatency(size):
	return MRAM_READ_ALPHA + 0.5 * size


def write_mramLatency(size):
	return MRAM_WRITE_ALPHA + 0.5 * size


def hostToDPUTransfer(size):
	return (size * 1.0 / HOST_TO_DPU_BW) * DPU_CLOCK_SPEED


def DPUToHostTransfer(size):
	return (size * 1.0 / DPU_TO_HOST_BW) * DPU_CLOCK_SPEED


def getInternalCycles(PartitionSize, CyclesPerByte):
	return (PartitionSize * 1.0 / WRAM_SIZE) * (read_mramLatency(WRAM_SIZE) + write_mramLatency(WRAM_SIZE) + WRAM_SIZE*CyclesPerByte)


def getExternalCycles(PartitionSize):
	return hostToDPUTransfer(PartitionSize) + DPUToHostTransfer(PartitionSize)


#def selectJob(JobList: list[Job]) -> Job:
#	global sim
#	for job in JobList:
#		if job.WorkLoadDispatched < job.WorkLoadSize:
#			return job
#
#	return None


def main():
	global sim

	TaskPower = int(sys.argv[1])

	sim.TaskSize = 2**TaskPower

	print("Task Power :", TaskPower)

	sim.JobList = [Job(2**27, 0, 70.0/8), Job(2**25, 0,
                                           70.0/8), Job(2**26, 0, 70.0/8)]
	sim.OutQueue = []
	sim.InQueue = []

	sim.TaskArray = []
	for i in range(int(MRAM_SIZE/sim.TaskSize)):
		sim.TaskArray.append(Task(i, 0, 0, 0))

	#sim.fillInQueue_RR()
	sim.fillInQueue_FCFS()

	#Simulation loop
	while sim.JobList:
		sim.TotalCycles += SIM_CYCLES

		#Simulate memory bus transfers
		sim.SimMemoryBus()

		#Simulate taks on DPU
		sim.SimDPU()

	print("TotalCycles :", sim.TotalCycles)


if __name__ == "__main__":
	main()
