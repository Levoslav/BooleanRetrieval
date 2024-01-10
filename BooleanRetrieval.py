#!/usr/bin/env python3

import xml.etree.ElementTree as ET
import argparse
import re 
import os
import io

parser = argparse.ArgumentParser()
parser.add_argument("--language", default="cz", type=str, help="Language of xml files")

class WordIndex:
    def __init__(self):
        self.dictionary = {} # Dictionary with words as a keys and list of strings(IDs) as values 
        self.alphabet = set() # Alphabet of all IDs that occureds
        
    def add(self, doc_id, text):
        tokens = re.findall(r'\b\w+\b', text)
        self.alphabet.add(doc_id) # Add ID to the alphabet
        for token in tokens:
            if token not in self.dictionary:
                self.dictionary[token] = set()
            self.dictionary[token].add(doc_id)
            
    def get(self,word): # Return list of IDs if word not found, return empty list
        return self.dictionary[word] if word in self.dictionary else []

    def finish(self): # When done adding, transform all sets to lists and sort them 
        for k in self.dictionary.keys():
            self.dictionary[k] = sorted(list(self.dictionary[k]))

class Parser:
    def __init__(self,WI): # Object of type WordIndex needed during init
        self.alphabet = WI.alphabet
        self.WI = WI
        
    def evaluate_query(self,query):
        query = query.strip()
        tokens = re.findall(r'\(|\)|AND|OR|NOT|\b\w+\b', query)
        #print(tokens)
        for i in range(len(tokens)): # Convert words to the lists of IDs
            if tokens[i] in {"AND","OR","NOT","(",")"}:
                pass 
            else:
                tokens[i] = self.WI.get(tokens[i])
        
        # Shunting yard algo 
        # Assuming the expression is in the correct form 
        stack = []
        postfix = []

        for token in tokens:
            if type(token) == list:# Move list to the postfix
                postfix.append(token)
            elif token == "(":
                stack.append(token)
            elif token == ")":
                while stack[-1] != "(":
                    postfix.append(stack.pop()) # Move the predicate from {AND,OR,NOT} to the postfix expression
                stack.pop() # Remove "(" from the stack 
            elif token in {"AND","OR"}:
                while len(stack) > 0 and (stack[-1] in {"AND","OR","NOT"}):
                    postfix.append(stack.pop()) # Move all AND,OR,NOT to the postfix
                stack.append(token) # Move the token to the stack
            elif token == "NOT":  
                if len(stack) > 0 and stack[-1] == "NOT": # NOT NOT True -> True
                    stack.pop()
                else:
                    stack.append(token)
                
        if len(stack) != 0:
            stack.reverse()
            postfix = postfix + stack

        stack = []
        
        for token in postfix:
            if type(token) == list:
                stack.append(token)
            elif token == "AND":
                l2 = stack.pop()
                l1 = stack.pop()
                stack.append(AND(l1,l2))
            elif token == "OR":
                l2 = stack.pop()
                l1 = stack.pop()
                stack.append(OR(l1,l2))
            elif token == "NOT":
                l1 = stack.pop()
                stack.append(NOT(l1,self.alphabet))

        if len(stack) != 1:
            print("ERROR")
        else:
            return stack.pop()

        

def AND(list_1, list_2): # Assuming list_1 and list_2 are sorted
    result = []
    i, j = 0, 0
    while i < len(list_1) and j < len(list_2): # Iterate while both lists have elements left
        if list_1[i] == list_2[j]:
            result.append(list_1[i])
            i += 1
            j += 1
        elif list_1[i] < list_2[j]:
            i += 1
        else:
            j += 1
    return result

def OR(list_1, list_2):
    return sorted(list(set(list_1 + list_2)))

def NOT(list_1, alphabet):
    complement = sorted([id for id in alphabet if id not in list_1])
    return complement

def reformat_xml(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:
        xml_heading = f.readline() + '\n' + f.readline()
        xml_content = f.read()
        
        # Replace all the trash that can appear in provided xml_files
        xml_content = re.sub(r'&dagger;', '†', xml_content)
        xml_content = re.sub(r'&copy;', ' ', xml_content)
        xml_content = re.sub(r'&int;', ' ', xml_content)
        xml_content = re.sub(r'&euro;', '€', xml_content)
        xml_content = re.sub(r'<CENTER>', '<ccenter>', xml_content)
        xml_content = re.sub(r'</CENTER>', '<ccenter>', xml_content)
        xml_content = re.sub(r'IMG', 'img', xml_content) 
        xml_content = re.sub(r'<A ', '<aa ', xml_content)
        xml_content = re.sub(r'</A>', '<aa>', xml_content) 
        xml_content = re.sub(r'\x0e', ' ', xml_content)
        xml_content = re.sub(r'</LATIMES2002></LATIMES2002>', '</LATIMES2002>',xml_content)
        xml_content.replace('&','&amp;')
        xml_content = re.sub(r'<[^A-Z/]', '&lt;', xml_content) # Replace all occurences of "<" followed by any other character but capital lette or "/"
        
        return xml_heading + '\n' + xml_content

def evaluate_file(query_file_name, target_file_name, Parser, output_file_name):
    xml_file = ET.parse(query_file_name)
    queries = []
    for query_tag in xml_file.findall("top"):
        query_num = query_tag.find("num").text
        query = query_tag.find("query").text
        queries.append((query_num, Parser.evaluate_query(query)))
        
    # Save it to the output_file 
    with open(output_file_name, 'w', encoding='utf-8') as f:
        for query_num, query_result in queries:
            for doc_id in query_result:
                f.write(query_num + " " + doc_id + "\n")

    # Compute precision and recall 
    targets_dict = dict() # Key is query_ID , value is list of doc IDs 
    with open(target_file_name, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.split()
            query_ID = line[0]
            doc_id = line[2]
            doc_flag = line[3]
            if line[0] not in targets_dict:
                targets_dict[query_ID] = []
            if doc_flag == "1":
                targets_dict[query_ID].append(doc_id)
    

    prec_sum, recall_sum = 0, 0
    for query_ID, doc_IDs in queries:
        relevant_predicted = set(doc_IDs)
        relevant_true = set(targets_dict[query_ID])
        TP = len(relevant_predicted.intersection(relevant_true))
        FP = len(relevant_predicted.difference(relevant_true))
        FN = len(relevant_true.difference(relevant_predicted))
        prec = TP/ (TP + FP) if (TP + FP) != 0 else 0
        recall = TP / (TP + FN) if (TP + FN) != 0 else 0
        prec_sum += prec
        recall_sum += recall
        print(query_ID + "         Precision: " + str(prec)[:5] + "     Recall: " + str(recall)[:5] )
    print("Average precision: " + str(prec_sum/len(queries)) + "    Average recall: " + str(recall_sum/len(queries)) )


    

def main(args):
    
    cz_elements = ["TITLE","HEADING","TEXT"] # XML elemetns we want to examine in Czech texts.
    en_elements = ["HD", "LD", "TE"] # XML elements we want to examine in English texts.

    WI = WordIndex()
    

    dir_path = "A2/" + ("documents_cs" if args.language == "cz" else "documents_en")
    xml_files = [f for f in os.listdir(dir_path) if f.endswith(".xml")]
    for xml_file_name in xml_files:

        print(dir_path + "/" + xml_file_name)
        try: # Try creating an xml_file object but some files are filled with garbage so it might throw an exception 
            xml_file = ET.parse(dir_path + "/" + xml_file_name)
        except Exception as e: # Remove the garbage from the file and create xml_file from it's content 
            print("tu chyba^^")
            file_content = reformat_xml(dir_path + "/" + xml_file_name)
            xml_file = ET.parse(io.StringIO(file_content)) # Create file like object which can be parsed by ET.parse()

        for DOC in xml_file.findall("DOC"):
            
            doc_ID = DOC.find("DOCID").text
            
            for element_name in cz_elements if args.language == "cz" else en_elements:
                
                for tag in DOC.findall(element_name):
                    if tag.text != None:
                        WI.add(doc_ID, tag.text)
    WI.finish()
    print("--------WordIndex created--------")
    P = Parser(WI)
    queries_file_name = "A2/" + ("topics-train_cs.xml" if args.language == "cz" else "topics-train_en.xml")
    output_file_name = "result_cs.txt" if args.language == "cz" else "result_en.txt"
    targets_file_name = "A2/" + ("qrels-train_cs.txt" if args.language == "cz" else "qrels-train_en.txt")
    evaluate_file(query_file_name=queries_file_name,
                   target_file_name=targets_file_name,
                     Parser=P,
                       output_file_name=output_file_name) # Create output file and print precission and recall for all queries on stdout
    print("--------done--------")

        


if __name__ == "__main__":
    args = parser.parse_args([] if "__file__" not in globals() else None)
    main(args)