# -*- coding: utf-8 -*-
import sys
import os
from typing import Optional
from mdtraj.geometry import distance
from torch import Tensor
currentUrl = os.path.dirname(__file__)
parentUrl = os.path.abspath(os.path.join(currentUrl, os.pardir))
sys.path.append(parentUrl)
from generator.graphomer_20220111 import Graphomer_20220111,accuracy
import mdtraj as md
import sys
sys.path.append('../data')
from graph import *
from protein import *
import time

#added by witty 20220718
def real_pdb_length(pdb_name):
    pdb_name_bak = pdb_name.split('.pdb')[0] + '.bak.pdb'
    top = md.load(pdb_name).topology
    atom = top.select("backbone and name CA")
    real_length = len(atom)
    print(real_length)

    if real_length > 400:
        os.system("cp %s  %s" % (pdb_name, pdb_name_bak))
        atom_end = top.atom(atom[400])
        print(atom_end)
        num = 0
        pdb_short = open(pdb_name, 'w')
        with open(pdb_name_bak) as file1:
            for line in file1:
                each = line.strip().split()
                if each[0] == "ATOM":
                    num += 1
                if each[0] == "ATOM" and num >= 1 and each[3] == str(atom_end).split("-")[0][:3] and each[5] == str(atom_end).split("-")[0][3:]:
                    break
                if num >= 1:
                    pdb_short.write(line)
        pdb_short.close()
    return real_length

def create_fasta_files(predict,length,acc,folder_name,index):
    # file_name = folder_name + "/" + folder_name + "_" + str(index) + ".fasta"
    file = open(file_name,"w")
    file.write("> predicted model "+folder_name+"\tacc: "+str(acc)+"\tlength: "+str(length)+"\n")
    count = 0
    for i in range(0,length):
        if(predict[i] in seq_re_dir.keys()):
            residue = seq_re_dir[predict[i]]
            file.write(residue)
            count += 1
            if (count == 71):
                file.write("\n")
                count = 0
        else:
            residue = 'X'
            file.write(residue)
    file.close()

def write_fasta(output_dir,predict,length,acc,protein_name,index):
    file_name = protein_name + ".fasta"
    file = open(os.path.join(output_dir, file_name),"a")
#    file.write("> predicted model"+"_"+str(index)+"\t"+protein_name+"\tacc: "+str(acc)+"\tlength: "+str(length)+"\n")
    file.write("> predicted model"+"_"+str(index)+"\tacc: "+str(acc)+"\tlength: "+str(length)+"\n")
    count = 0
    for i in range(0,length):
        if(predict[i] in seq_re_dir.keys()):
            residue = seq_re_dir[predict[i]]
            file.write(residue)
            count += 1
            if (count == 71):
                file.write("\n")
                count = 0
        else:
            residue = "X"
            file.write(residue)
    file.write("\n")
    file.close()
    return


def create_mask(seqs,design_dict: dict):
    seq_one_dict = {
    'A':1,
    'R':2,
    'N':3,
    'D':4,
    'C':5,
    'Q':6,
    'E':7,
    'G':8,
    'H':9,
    'I':10,
    'L':11,
    'K':12,
    'M':13,
    'F':14,
    'P':15,
    'S':16,
    'T':17,
    'W':18,
    'Y':19,
    'V':20
    }
    seqs_mask = torch.zeros(size=seqs.shape,dtype=torch.long)
    for seq_num in design_dict:
        seqs_mask[0,seq_num] = seq_one_dict[design_dict[seq_num]]
    
    return seqs_mask

def run_single_protein(output_dir,pdb_name,times,design_dict : dict = None, create_fasta=False):
    #get features
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    top = md.load(pdb_name).topology
    t = md.load(pdb_name)
    distance, movement, quate = compute_rotation_movment(traj=t,top=top,length=400)
    phipsi, DSSP, mask = compute_phipsi_DSSP(top=top,t=t,length=400)
    seqs = get_seq(top=top,length=400)
    path_length, centerity = compute_shortestpath_centerilty(distances=distance,length=400)
    distance = distance.float()
    movement = movement.float()
    quate = quate.float()
    phipsi = torch.from_numpy(phipsi).float()
    DSSP = torch.from_numpy(DSSP).long()
    mask = torch.from_numpy(mask).bool()
    seqs = torch.from_numpy(seqs).long()
    path_length = torch.from_numpy(path_length).float()
    centerity = torch.from_numpy(centerity).float()
    distance = distance.unsqueeze(0)
    movement = movement.unsqueeze(0)
    quate = quate.unsqueeze(0)
    phipsi = phipsi.unsqueeze(0)
    DSSP = DSSP.unsqueeze(0)
    mask = mask.unsqueeze(0)
    seqs = seqs.unsqueeze(0)
    path_length = path_length.unsqueeze(0)
    centerity = centerity.unsqueeze(0)

    #find device
    use_gpu = torch.cuda.is_available()
    device = torch.device("cuda" if use_gpu else "cpu")

    #load model
    model = Graphomer_20220111().to(device)
    state_dict = torch.load("../models/20220607_random_3.pkl",map_location='cpu')
    model.load_state_dict(state_dict)

    if create_fasta:
        ##################### add by witty #####################
        # protein_name = pdb_name.split('/')[-1].split('.')[0]
        # file_name = protein_name + ".fasta"
        # print(pdb_name)
        protein_name = pdb_name.split('/')[-1].split('.pdb')[0]
        file_name = protein_name + ".fasta"
        #######################################################
        try:
            os.remove(file_name)
        except:
            pass
        length = 0
        for residue in top.residues:
            length += 1

    with torch.no_grad():
        if(use_gpu):
            phipsi = phipsi.cuda()
            DSSP = DSSP.cuda()
            centerity = centerity.cuda()
            distance = distance.cuda()
            path_length = path_length.cuda()
            movement = movement.cuda()
            quate = quate.cuda()
            mask = mask.cuda()
        distance = torch.unsqueeze(distance,dim=-1) #(30966,400,400) -> (30966,400,400,1)
        path_length = torch.unsqueeze(path_length,dim=-1) #as top
        src_mask = torch.cat([distance*0,distance,path_length,movement,quate],dim=-1) #(30966,400,400,10)
        test_accs = []
        #added by witty 20220806
        result_dic = {}
        for i in range(0,times):
            seqs = seqs.cpu()
            rand_seed = torch.rand(size=(seqs.shape[0],seqs.shape[1],1))
            if(design_dict is None):
                seqs_zeros = torch.zeros(size=seqs.shape,dtype=torch.long)
                seqs_rand = torch.rand(size=seqs.shape)
                seqs_mask = torch.where(seqs_rand>1.0,seqs,seqs_zeros)
            else:
                seqs_mask = create_mask(seqs=seqs,design_dict=design_dict)
                pass
            if(use_gpu):
                seqs = seqs.cuda()
                seqs_mask = seqs_mask.cuda()
                rand_seed = rand_seed.cuda()
            output = model(phipsi=phipsi,DSSP=DSSP,centerity=centerity,rand_seed=rand_seed,tgt=seqs_mask,src_mask=src_mask,padding_mask=mask)
            output = output[0:].view(-1,output.shape[-1])
            label = seqs[0:].view(-1)
            predict = output.max(1)
            acc_test = accuracy(predict=predict,label=label)
            test_accs.append(acc_test)

            # added by witty 20220806
            result_dic[i] = [predict[1].cpu().numpy(), length, acc_test, protein_name]
#            if create_fasta:
#                predict = predict[1].cpu().numpy()
#                write_fasta(predict=predict,length=length,acc=acc_test,protein_name=protein_name,index=i)          
    # return test_accs
        
        if create_fasta:
            file_name = protein_name + ".fasta"
            try:
                os.remove(os.path.join(output_dir, file_name))
            except:
                print()
            sorted_id = sorted(range(len(test_accs)), key=lambda k: test_accs[k], reverse=True)
            num = 0
            for j in sorted_id:
                write_fasta(output_dir, predict=result_dic[j][0], length=result_dic[j][1], acc=result_dic[j][2], protein_name=result_dic[j][3], index=num)
                num += 1
    #added by witty
    recovery = "%.3f"%(np.mean(test_accs))
    return recovery, length

def generate_single_protein(pdb_name,times=10,create_fasta=False):
    #get features
    top = md.load(pdb_name).topology
    t = md.load(pdb_name)
    distance_value, movement_vector, quater_number = compute_rotation_movment(traj=t,top=top,length=400)
    phipsi, DSSP, mask = compute_phipsi_DSSP(top=top,t=t,length=400)
    seq = get_seq(top=top,length=400)
    path_length, centerity = compute_shortestpath_centerilty(distances=distance_value,length=400)
    distance_value = distance_value.float()
    movement_vector = movement_vector.float()
    quater_number = quater_number.float()
    phipsi = torch.from_numpy(phipsi).float()
    DSSP = torch.from_numpy(DSSP).long()
    mask = torch.from_numpy(mask).bool()
    seq = torch.from_numpy(seq).long()
    path_length = torch.from_numpy(path_length).float()
    centerity = torch.from_numpy(centerity).float()
    distance_value = distance_value.unsqueeze(0)
    movement_vector = movement_vector.unsqueeze(0)
    quater_number = quater_number.unsqueeze(0)
    phipsi = phipsi.unsqueeze(0)
    DSSP = DSSP.unsqueeze(0)
    mask = mask.unsqueeze(0)
    seq = seq.unsqueeze(0)
    path_length = path_length.unsqueeze(0)
    centerity = centerity.unsqueeze(0)

    #find device
    use_gpu = torch.cuda.is_available()
    device = torch.device("cuda" if use_gpu else "cpu")

    #load model
    model = Graphomer_20220111().to(device)
    state_dict = torch.load("../models/20220607_random_3.pkl", map_location='cpu')
    model.load_state_dict(state_dict)

    #run model
    with torch.no_grad():
        if(use_gpu):
            seq = seq.cuda()
            seq_mask = seq.cuda()
            phipsi = phipsi.cuda()
            DSSP = DSSP.cuda()
            centerity = centerity.cuda()
            distance_value = distance_value.cuda()
            path_length = path_length.cuda()
            movement_vector = movement_vector.cuda()
            quater_number = quater_number.cuda()
            mask = mask.cuda()
        distance_value = torch.unsqueeze(distance_value,dim=-1) #(30966,400,400) -> (30966,400,400,1)
        path_length = torch.unsqueeze(path_length,dim=-1) #as top
        src_mask = torch.cat([distance_value*0,distance_value,path_length,movement_vector,quater_number],dim=-1) #(30966,400,400,10)
        if create_fasta:
            folder_name = pdb_name.split('/')[-1].split('.')[0]
            dir_list = os.listdir()
            if folder_name in dir_list:
                pass
            else:
                os.mkdir(folder_name)
            length = 0
            for residue in top.residues:
                length += 1
            for i in range(0,times):      
                rand_seed = torch.rand(size=(seq.shape[0],seq.shape[1],1))       
                rand_seed = rand_seed.cuda()            
                output = model(phipsi=phipsi,DSSP=DSSP,centerity=centerity,rand_seed=rand_seed,tgt=seq_mask,src_mask=src_mask,padding_mask=mask)
                output = output[0:].view(-1,output.shape[-1])
                label = seq[0:].view(-1)
                predict = output.max(1)
                acc_test = accuracy(predict=predict,label=label)
                predict = predict[1].cpu().numpy()
                create_fasta_files(predict=predict,length=length,acc=acc_test,folder_name=folder_name,index=i)
        else:
            for i in range(0,times):
                rand_seed = torch.rand(size=(seq.shape[0],seq.shape[1],1))       
                rand_seed = rand_seed.cuda()         
                output = model(phipsi=phipsi,DSSP=DSSP,centerity=centerity,rand_seed=rand_seed,tgt=seq_mask,src_mask=src_mask,padding_mask=mask)
                output = output[0:].view(-1,output.shape[-1])
                label = seq[0:].view(-1)
                predict = output.max(1)
                acc_test = accuracy(predict=predict,label=label)
        return 


    

# if __name__ == "__main__":
    #generate_single_protein("../data/test_sc/2ys8A00.pdb",times=10,create_fasta=True)
    #generate_single_protein("./3com.pdb",times=10,create_fasta=True)
    # example_dict={
    #     0:'V',
    #     4:'L',
    #     14:'A'
    # }
    # run_single_protein(pdb_name="./3com.pdb",times=100,design_dict=example_dict,create_fasta=True)
    # recovery, length = run_single_protein('/root/proteindesign/Graphomer/result/ef61e0554b4cb6a24003490d784a6579/upload.pdb', times=2, design_dict=None, create_fasta=True)
    # print(recovery)
