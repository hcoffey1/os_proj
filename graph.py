import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

directory = "./sim_out/base3x/"

def main():


	dataList = []


	for file in os.listdir(directory):

		if os.path.isdir(directory+file):
			continue

		with open(directory + file) as f:
			for l in f.readlines():
				l = l.split()
				if l[0] == "Task" and l[1] == "Power":
					power = int(l[3])

				if l[0] == '---':
					tmpJobIdx = int(l[3])
					if tmpJobIdx == 0:
						job0_cycles = int(float(l[8]))

					elif tmpJobIdx == 1:
						job1_cycles = int(float(l[8]))

					else:
						job2_cycles = int(float(l[8]))


				if l[0] == "TotalCycles":
					totalCycles = int(float(l[2]))

					dataList.append([power, totalCycles, job0_cycles, job1_cycles, job2_cycles])
	
	df = pd.DataFrame(dataList, columns=['TaskSize', 'TotalCycles', 'Job0Cycles', 'Job1Cycles', 'Job2Cycles'])
	df = df.sort_values(by=['TaskSize'], ascending=True)
	print(df)

	sns.barplot(data=df, x='TaskSize', y='TotalCycles')
	plt.show()
if __name__ == "__main__":
	main()