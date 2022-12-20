SIM_CYCLES = 1e6



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

	ParentJob : Job = None

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

class SimState:
#	InternalDMAActive = False

	DPUActive = False
	ActiveTask : Task = None

	MemoryBusActive = False
	MemoryBusTask : Task = None

	TaskSize = 0

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

def selectJob(JobList : list[Job]) -> Job:
	global sim
	for job in JobList:
		if job.WorkLoadDispatched < job.WorkLoadSize:
			return job

	return None 

def selectTask(TaskList : list[Task]) -> Task:
	global sim
	for task in TaskList:
		if task.Valid and not task.Active and not task.Transfering and task.InternalCyclesRemaining > 0:
			return task

	return None

def pruneJobs(JobList : list[Job]) -> None:
	modified = True 

	while modified:
		modified = False
		for job in JobList:
			if job.WorkLoadCompleted >= job.WorkLoadSize:
				JobList.remove(job)
				modified = True


def main():

	##print((2**23)/WRAM_SIZE)
	##print(read_mramLatency(WRAM_SIZE))
	##print(write_mramLatency(WRAM_SIZE))

	#x=0
	#WorkLoadSize = 2**26
	#PartitionSize = 2**23
	#CyclesPerByte = 30.0/8
	#for i in range(int((WorkLoadSize) / (PartitionSize))):
	#	print(getExternalCycles(PartitionSize)/(1e6))
	#	print(getInternalCycles(PartitionSize, CyclesPerByte)/(1e6))
	#	x += max(getExternalCycles(PartitionSize), getInternalCycles(PartitionSize, CyclesPerByte))
	#	print(i)

	#print("8MB", x/(1e6))

	#x=0
	#WorkLoadSize = 2**26
	#PartitionSize = 2**24
	#CyclesPerByte = 30.0/8
	#for i in range(int((WorkLoadSize) / (PartitionSize))):
	#	print(getExternalCycles(PartitionSize)/(1e6))
	#	print(getInternalCycles(PartitionSize, CyclesPerByte)/(1e6))
	#	print(i)
	#	x += max(getExternalCycles(PartitionSize), getInternalCycles(PartitionSize, CyclesPerByte))

	#print("16MB", x/(1e6))

	#x=0
	#WorkLoadSize = 2**26
	#PartitionSize = 2**25
	#CyclesPerByte = 30.0/8
	#for i in range(int((WorkLoadSize) / (PartitionSize))):
	#	print(getExternalCycles(PartitionSize)/(1e6))
	#	print(getInternalCycles(PartitionSize, CyclesPerByte)/(1e6))
	#	print(i)
	#	x += max(getExternalCycles(PartitionSize), getInternalCycles(PartitionSize, CyclesPerByte))

	#print("32MB", x/(1e6))

	#x=0
	#WorkLoadSize = 2**26
	#PartitionSize = 2**26
	#CyclesPerByte = 30.0/8
	#for i in range(int((WorkLoadSize) / (PartitionSize))):
	#	print(getExternalCycles(PartitionSize)/(1e6))
	#	print(getInternalCycles(PartitionSize, CyclesPerByte)/(1e6))
	#	print(i)
	#	x += max(getExternalCycles(PartitionSize), getInternalCycles(PartitionSize, CyclesPerByte))


	#print("64MB", x/(1e6))

	global sim

	sim.TaskSize = 2**23

	TotalCycles = 0
	JobList = [Job(2**26, 0, 3.0/8)]
	OutQueue = []
	InQueue = []

	TaskArray = []
	for i in range(int(MRAM_SIZE/sim.TaskSize)):
		TaskArray.append(Task(i, 0, 0, 0))

	#Simulation loop
	while JobList: 
		TotalCycles += SIM_CYCLES

		#if outbound task waiting, start its transfer
		if not sim.MemoryBusActive and OutQueue:
			print("Starting transfer back to host")
			sim.ActiveTask.Transfering = True

			sim.MemoryBusTask = OutQueue.pop(0)
			sim.MemoryBusActive = True

		#if memory bus is active, continue whatever transfer is happening
		if sim.MemoryBusActive:
			sim.MemoryBusTask.TransferCyclesRemaining -= SIM_CYCLES

			if sim.MemoryBusTask.TransferCyclesRemaining <= 0:
				print("Done transfering to host...")

				if sim.MemoryBusTask.IsToHost:
					sim.MemoryBusTask.ParentJob.WorkLoadCompleted += sim.TaskSize
					print("Job has finished : ", sim.MemoryBusTask.ParentJob.WorkLoadCompleted, '/', sim.MemoryBusTask.ParentJob.WorkLoadSize)
					#break

				sim.MemoryBusTask.Transfering = False
				sim.MemoryBusTask = None
				sim.MemoryBusActive = False

		#if need to read from host
		elif not sim.MemoryBusActive:

			#Is there a spot available on the DPU?
			FreeTask = getFreeTask(TaskArray)

			#Is there a Job waiting in queue?
			NextJob = selectJob(JobList)

			if FreeTask != None and NextJob != None:
				
				print("Starting transfer of job ", NextJob.ID)
				#Associate Task with Job, and mark as transfering to DPU
				FreeTask.ParentJob = NextJob
				FreeTask.CyclesPerByte = NextJob.CyclesPerByte
				FreeTask.TransferCyclesRemaining = hostToDPUTransfer(sim.TaskSize) - SIM_CYCLES
				FreeTask.InternalCyclesRemaining = getInternalCycles(sim.TaskSize, FreeTask.CyclesPerByte)
				FreeTask.Transfering = True
				FreeTask.Valid = True

				#Record that job has dispatched a task
				NextJob.WorkLoadDispatched += sim.TaskSize

				#Let global state know memory bus is active
				sim.MemoryBusActive = True
				sim.MemoryBusTask = FreeTask


		#if need to start a task 
		if not sim.DPUActive:

			#Is there a task that needs to be run?
			NextTask : Task = selectTask(TaskArray)

			if NextTask != None:
				print("Starting task ", NextTask.TaskID, ", job ID: ", NextTask.ParentJob.ID)
				NextTask.Active = True
				#NextTask.InternalCyclesRemaining = getInternalCycles(sim.TaskSize, NextTask.CyclesPerByte) - SIM_CYCLES

				sim.ActiveTask = NextTask
				sim.DPUActive = True

		#Process currently running task
		if sim.ActiveTask != None:
			sim.ActiveTask.InternalCyclesRemaining -= SIM_CYCLES

			#If task has finished, begin transfering it back to Host
			if sim.ActiveTask.InternalCyclesRemaining <= 0:
				print("Done")

				sim.ActiveTask.Active = False

				sim.ActiveTask.TransferCyclesRemaining = DPUToHostTransfer(sim.TaskSize)
				sim.ActiveTask.IsToHost = True

				#Start transfer
				if not sim.MemoryBusActive:
					print("Starting transfer back to host")
					sim.ActiveTask.Transfering = True

					sim.MemoryBusTask = sim.ActiveTask
					sim.MemoryBusActive = True
				
				#Bus is currently busy, put task in outbound queue
				else:
					OutQueue.append(sim.ActiveTask)


				sim.DPUActive = False
				sim.ActiveTask = None

		pruneJobs(JobList)
	
	print(TotalCycles)




if __name__ == "__main__":
	main()