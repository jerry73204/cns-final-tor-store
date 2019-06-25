import pickle
import json
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

def main():

    table = {}
    with open("duration300.txt",'r') as f:
        pos = f.tell()
        while True:
            line = f.readline()
            new_pos = f.tell()
            if pos ==new_pos:
                break
            else:
                pos = new_pos
                lines = line.strip().split(' ')
                time = float(lines[0])
                id_ = lines[1]
                action = lines[2]

                try :
                    table[id_]
                except :
                    table[id_] = {}
                if action == "retrieved":
                    try : 
                        table[id_]["retrieved"]
                    except:
                        table[id_]["retrieved"] = []
                    table[id_]["retrieved"].append(time)
                elif action == "failed":
                    try : 
                        table[id_]["failed"]
                    except:
                        table[id_]["failed"] = []
                    table[id_]["failed"].append(time)
                else:
                    table[id_][action]=time
                if action == "stored":
                    table[id_]["key"] = lines[3]
    # failed/retrieved
    failed = []
    for key in table.keys():
        try :
            f = len(table[key]["failed"])
            r = len(table[key]["retrieved"])
            t = f/(f+r) * 100 
            t = t//1
            failed.append(t)
        except:
            continue

  
    plt.hist(failed,bins=100,range=(0,100))
    # plt.plot(x,y)
    plt.xlabel("percent %")
    plt.ylabel("num")
    plt.title("Failed rate")
    plt.savefig("png/failed_rate.png",dpi=300)
    plt.close()
    
    
    # avg failed
    failed = []
    for key in table.keys():
        try :
            num = len(table[key]["failed"])
            t = (table[key]["failed"][-1]- table[key]["stored"])//60
            failed.append(t/num)
        except:
            continue

  
    plt.hist(failed,bins=100,range=(0,400))
    # plt.plot(x,y)
    plt.xlabel("minute")
    plt.ylabel("num")
    plt.title("Average failed time")
    plt.savefig("png/avg_failed.png",dpi=300)
    plt.close()

    # live time
    failed = []

    for key in table.keys():
        try :
            t = (table[key]["retrieved"][-1]- table[key]["retrieved"][0])//60
            failed.append(t)
        except:
            continue

    plt.hist(failed,bins=100,range=(0,1600))
    plt.xlabel("minute")
    plt.ylabel("num")
    plt.title("Live time")
    plt.savefig("png/live_time.png",dpi=300)
    plt.close()

    # First retrieved time
    retrieved = []
    count = 0
    for key in table.keys():
        try :
            t = (table[key]["retrieved"][0]-table[key]["stored"])//60
            retrieved.append(t)
        except:
            continue

    plt.hist(retrieved,bins=100,range=(0,70))
    plt.xlabel("minute")
    plt.ylabel("num")
    plt.title("First retrieved time")
    plt.savefig("png/retrieved_time.png",dpi=300)
    plt.close()


    # stored time
    retrieved = []
    count = 0
    for key in table.keys():
        try :
            t = (table[key]["stored"]-table[key]["start"])//60
            retrieved.append(t)
        except:
            continue


    plt.hist(retrieved,bins=100,range=(0,250))
    plt.xlabel("minute")
    plt.ylabel("num")
    plt.title("Stored time")
    plt.savefig("png/stored_time.png",dpi=300)
    plt.close()



if __name__ == "__main__":
    main()