import bottle
from bottle import route, run, hook, response, request, static_file, template
import collections

import sys
import os
import argparse
import numpy as np
import json
from sklearn.datasets import fetch_20newsgroups
from sklearn.metrics import accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn import linear_model
from sklearn import tree
from sklearn import svm
from sklearn.metrics import confusion_matrix
import time
import re
import argparse

def ListifyVector(v):
  # If the vector is all zeros, put a uniform on it.
  return [x for x in v]
def GetJsonExampleList(data, data_vectors, labels, classifier, tokenizer):
  out = []
  for i, doc in enumerate(data):
    temp = {}
    temp['features'] = ' \n '.join(map(lambda x: ' '.join(tokenizer(x)), doc.split('\n'))).split(' ')
    temp['true_class'] = int(labels[i])
    temp['predict_proba'] = ListifyVector(classifier.predict_proba(data_vectors[i])[0])
    temp['prediction'] = classifier.predict(data_vectors[i])[0]
    out.append(temp)
  return out

def GetParsedDocuments(data, tokenizer):
  out = []
  for i, doc in enumerate(data):
    temp = '\n'.join(map(lambda x: ' '.join(tokenizer(x)), doc.split('\n')))
    out.append(temp)
  return out
  
def GenerateJSON(class_names, train_data, train_vectors, train_labels, test_data, test_vectors, test_labels, classifier, vectorizer):
  # class_names is a list
  # train_data and test_data are assumed to be lists of strings
  # train_labels and test_labels are lists of ints
  # classifier is assumed to be a trained classifier
  # We will fit the vectorizer to the training data
  tokenizer = vectorizer.build_tokenizer()
  output = {}
  output['class_names'] = class_names
  output['feature_attributes'] = {}
  #predictions = classifier.predict(test_vectors)
  GeneralStatistics(class_names, train_data, train_vectors, train_labels, test_data, test_vectors, test_labels, classifier, tokenizer, output)
  FeatureStatistics(vectorizer.vocabulary_.keys(), class_names, train_vectors, train_labels, test_vectors, test_labels, vectorizer, output)
  return output

def UpdateJSON(json_map, words_to_consider, class_names, train_data, train_vectors, train_labels, test_data, test_vectors, test_labels, classifier, vectorizer):
  tokenizer = vectorizer.build_tokenizer()
  json_map['class_names'] = class_names
  GeneralStatistics(class_names, train_data, train_vectors, train_labels, test_data, test_vectors, test_labels, classifier, tokenizer, json_map)
  FeatureStatistics(words_to_consider, class_names, train_vectors, train_labels, test_vectors, test_labels, vectorizer, json_map)
  

def GeneralStatistics(class_names, train_data, train_vectors, train_labels, test_data, test_vectors, test_labels, classifier, tokenizer, output):
  # modifies output
  output['train'] = GetJsonExampleList(train_data, train_vectors, train_labels, classifier, tokenizer)
  output['test'] = GetJsonExampleList(test_data, test_vectors, test_labels, classifier, tokenizer)
  output['statistics'] = {}
  output['statistics']['train'] = {}
  output['statistics']['test'] = {}
  output['statistics']['train']['accuracy'] = round(accuracy_score(train_labels, classifier.predict(train_vectors)), 3)
  output['statistics']['test']['accuracy'] = round(accuracy_score(test_labels, classifier.predict(test_vectors)), 3)
  output['statistics']['train']['class_distribution'] = list(np.bincount(train_labels, minlength=len(class_names)).astype('float'))
  output['statistics']['test']['class_distribution'] = list(np.bincount(test_labels, minlength=len(class_names)).astype('float'))
  output['statistics']['test']['confusion_matrix'] = list(map(list,confusion_matrix(test_labels, classifier.predict(test_vectors))))
  output['statistics']['train']['confusion_matrix'] = list(map(list,confusion_matrix(train_labels, classifier.predict(train_vectors))))
def FeatureStatistics(word_list, class_names, train_vectors, train_labels, test_vectors, test_labels, vectorizer, output):
  train_count = np.bincount(train_vectors.nonzero()[1])
  test_count = np.bincount(test_vectors.nonzero()[1], minlength=len(train_count))
  for word in word_list:
    if word in output['feature_attributes']:
      del output['feature_attributes'][word]
    if word not in vectorizer.vocabulary_:
      continue
    i = vectorizer.vocabulary_[word]
    prob = float(train_count[i]) / train_labels.shape[0]
    test_freq = float(test_count[i]) / test_labels.shape[0]
    if prob > .01:
      train_nonzero = train_vectors.nonzero()[0][train_vectors.nonzero()[1] == i]
      test_nonzero = test_vectors.nonzero()[0][test_vectors.nonzero()[1] == i]
      output['feature_attributes'][word] = {}
      output['feature_attributes'][word]['train_freq'] = round(prob, 2)
      output['feature_attributes'][word]['test_freq'] = round(test_freq, 2)
      output['feature_attributes'][word]['train_distribution'] = np.bincount(train_labels[train_nonzero], minlength=len(class_names)).astype('float')
      output['feature_attributes'][word]['train_distribution'] /= sum(output['feature_attributes'][word]['train_distribution'])
      output['feature_attributes'][word]['train_distribution'] = ListifyVector(output['feature_attributes'][word]['train_distribution'])
      # not using this for now
      #output['feature_attributes'][word]['test_distribution'] = np.bincount(predictions[test_nonzero], minlength=len(class_names)).astype('float')
      #if test_count[i] > 0:
      #  output['feature_attributes'][word]['test_distribution'] /= sum(output['feature_attributes'][word]['test_distribution'])
      #output['feature_attributes'][word]['test_distribution'] = ListifyVector(output['feature_attributes'][word]['test_distribution'])
      output['feature_attributes'][word]['test_docs'] = list(test_nonzero.astype('str'))
      output['feature_attributes'][word]['train_docs'] = list(train_nonzero.astype('str'))


  
def LoadTextDataset(path_train, path_test):
  # Loads datasets from http://web.ist.utl.pt/acardoso/datasets/
  current_class = 0
  class_index = {}
  class_names = []
  train_data = []
  train_labels = []
  test_data = []
  test_labels = []
  for line in open(path_train):
    class_, text = line.split('\t') 
    if class_ not in class_index:
      class_index[class_] = current_class
      class_names.append(class_)
      current_class += 1
    train_data.append(text)
    train_labels.append(class_index[class_])
  for line in open(path_test):
    class_, text = line.split('\t') 
    test_data.append(text)
    test_labels.append(class_index[class_])
  return train_data, np.array(train_labels), test_data, np.array(test_labels), class_names
    


def LoadDataset(dataset_name):
  if dataset_name.endswith('ng'):
    if dataset_name == '2ng':
      cats = ['alt.atheism', 'soc.religion.christian']
      class_names = ['Atheism', 'Christianity']
    if dataset_name == '3ng':
      cats = ['comp.os.ms-windows.misc', 'comp.sys.ibm.pc.hardware', 'comp.windows.x']
      class_names = ['windows.misc', 'ibm.hardware', 'windows.x']
    newsgroups_train = fetch_20newsgroups(subset='train',categories=cats)
    newsgroups_test = fetch_20newsgroups(subset='test',categories=cats)
    train_data = newsgroups_train.data
    train_labels = newsgroups_train.target
    test_data = newsgroups_test.data
    test_labels = newsgroups_test.target
    return train_data, train_labels, test_data, test_labels, class_names
  if dataset_name == 'r8':
    return LoadTextDataset('/Users/marcotcr/phd/datasets/reuters/r8-train-all-terms.txt',
                    '/Users/marcotcr/phd/datasets/reuters/r8-test-all-terms.txt')
  if dataset_name == 'r52':
    return LoadTextDataset('/Users/marcotcr/phd/datasets/reuters/r52-train-all-terms.txt',
                    '/Users/marcotcr/phd/datasets/reuters/r52-test-all-terms.txt')
  if dataset_name == 'webkb':
    return LoadTextDataset('/Users/marcotcr/phd/datasets/webkb/webkb-train-stemmed.txt',
                    '/Users/marcotcr/phd/datasets/webkb/webkb-test-stemmed.txt')

    
# Right now, this is abs(P(Y) - P(Y | NOT x)). We probably want to normalize
# this, since these become pretty insignificant as text gets longer.
def WordImportance(classifier, example, inverse_vocabulary):
  orig = classifier.predict_proba(example)[0]
  imp = {}
  for i in example.nonzero()[1]:
    val = example[0,i]
    example[0,i] = 0
    pred = classifier.predict_proba(example)[0]
    imp[inverse_vocabulary[i]] = {}
    imp[inverse_vocabulary[i]]['weight'] = np.max(abs(pred - orig))
    imp[inverse_vocabulary[i]]['class'] = np.argmin(pred - orig)
    example[0,i] = val
  return imp

def MostImportantWord(classifier, v, class_):
  max_index = 0
  max_change = 0
  orig = classifier.predict_proba(v)[0][class_]
  for i in v.nonzero()[1]:
    val = v[0,i]
    v[0,i] = 0
    pred = classifier.predict_proba(v)[0][class_]
    change = orig - pred
    if change > max_change:
      max_change = change
      max_index = i
    v[0,i] = val
  if max_change <= 0:
    return -1
  return max_index

def ClassFlippers(classifier, v, class_):
  flippers = []
  orig = classifier.predict_proba(v)[0][class_]
  for i in v.nonzero()[1]:
    val = v[0,i]
    v[0,i] = 0
    pred = classifier.predict(v)[0]
    if pred != class_:
      pred = classifier.predict_proba(v)[0][class_]
      change = orig - pred
      flippers.append((i, change))
    v[0,i] = val
  return flippers
    
def WordImportanceGreedy(classifier, example, vectorizer, inverse_vocabulary):
  v = vectorizer.transform([example])
  class_ = classifier.predict(v)[0]
  new_class = class_
  imp = {}
  orig_weight = {}
  flippers = []
  while new_class == class_ and v.nonzero()[0].shape[0] > 0:
    i = MostImportantWord(classifier, v, class_)
    if i == -1:
      break
    orig_weight[i] = v[0,i]
    v[0,i] = 0
    new_class = classifier.predict(v)[0]
    if new_class != class_:
      v[0,i] = orig_weight[i]
      flippers = ClassFlippers(classifier, v, class_)
      v[0,i] = 0
  for i, change in flippers:
    imp[inverse_vocabulary[i]] = {}
    imp[inverse_vocabulary[i]]['weight'] = change
    imp[inverse_vocabulary[i]]['class'] = class_

  orig = classifier.predict_proba(v)[0][class_]
  for i,o in orig_weight.iteritems():
    v[0,i] = o
    pred = classifier.predict_proba(v)[0][class_]
    change = pred - orig
    if change > 0:
      imp[inverse_vocabulary[i]] = {}
      imp[inverse_vocabulary[i]]['weight'] = change
      imp[inverse_vocabulary[i]]['class'] = class_
    v[0,i] = 0
  return imp

# TODO
def MostImportantSequence(classifier, ex_list, vectorizer, class_):
  sentences = []
  current_start = 0
  current_max = 0
  current_answer = (-1,-1)
  previous_val = 0
  word_val = []
  for i in range(len(ex_list)):
    doc = ' '.join(ex_list[current_start:(i+1)])
    v = vectorizer.transform([doc])
    val = classifier.predict_proba(v)[0][class_] - 0.05 * (i - current_start)
    word_val.append(val - previous_val)
    if classifier.predict(v)[0] != class_ or val < 0:
      current_start = i + 1
      current_max = 0
      previous_val = 0
      continue
    if val > current_max:
      current_answer = (current_start, i+1)
      current_max = val
  sentence_importance = collections.defaultdict(lambda: 0.)
  total = 0
  for word, val in zip(ex_list[slice(*current_answer)], word_val[slice(*current_answer)]):
    if val > 0:
      sentence_importance[word] = val
      total += val
  for word in sentence_importance:
    sentence_importance[word] /= total
  return current_answer, sentence_importance
def WordImportanceSentenceGreedy(classifier, example, vectorizer, inverse_vocabulary):
  # Caution: we assume bag of words, as we re-add the sentences to the end of
  # the document.
  orig_v = vectorizer.transform([example])
  class_ = classifier.predict(orig_v)[0]
  new_class = class_
  ex = example.split()
  sentences = []
  sentence_importances = []
  words = set()
  while new_class == class_ and len(ex) > 0 :
    best, s_imp = MostImportantSequence(classifier, ex, vectorizer, class_)
    if best == (-1, -1):
      break
    sentences.append(ex[slice(*best)])
    sentence_importances.append(s_imp)
    del ex[slice(*best)]
    v = vectorizer.transform([' '.join(ex)])
    new_class = classifier.predict(v)[0]
  v = vectorizer.transform([' '.join(ex)])
  orig = classifier.predict_proba(v)[0][class_]
  imp = {}
  for s, s_imp in zip(sentences, sentence_importances):
    v = vectorizer.transform([' '.join(ex) + ' '.join(s)])
    pred = classifier.predict_proba(v)[0][class_]
    change = pred - orig
    for word in s_imp:
      if word not in imp:
        imp[word] = {}
        imp[word]['class'] = class_
        imp[word]['weight'] = 0
      imp[word]['weight'] += s_imp[word] * change
  return imp

def enable_cors(fn):
    def _enable_cors(*args, **kwargs):
        # set CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
        if bottle.request.method != 'OPTIONS':
            # actual request; reply with the actual response
            return fn(*args, **kwargs)
    return _enable_cors
def main():
  parser = argparse.ArgumentParser(description='Visualize some stuff')
  parser.add_argument('-json', '-j', type=str, help='generate json file')
  parser.add_argument('-loadjson', '-l', type=str, help='load json file')
  parser.add_argument('-dataset', '-d', type=str, help='2ng for Christianity vs Atheism, 3ng for Windows misc, IBM hardward and Windows X,', default='2ng')
  parser.add_argument('-classifier', '-c', type=str, help='logistic for logistic regression, svm for svm', default='logistic')
  args = parser.parse_args()
  global train_vectors, train_labels, test_vectors, test_labels, classifier, tokenizer, parsed_train, parsed_test, json_map, class_names, inverse_vocabulary
  train_data, train_labels, test_data, test_labels, class_names = LoadDataset(args.dataset)
  dataset_json = {'2ng' : '2ng.json', '3ng':'3ng.json', 'r8': 'r8.json', 'r52':'r52.json', 'webkb' : 'webkb.json'}
  vectorizer = CountVectorizer(lowercase=False)
  if args.classifier == 'logistic':
    classifier = linear_model.LogisticRegression(fit_intercept=True)
  elif args.classifier == 'svm':
    classifier = svm.SVC(probability=True)
  else:
    print 'ERROR: classifier must be logistic'
    quit()
  print 'Starting... done'
  train_vectors = vectorizer.fit_transform(train_data)
  test_vectors = vectorizer.transform(test_data)
  print 'Fitting classifier...',
  classifier.fit(train_vectors, train_labels)
  print 'done'
  terms = np.array(list(vectorizer.vocabulary_.keys()))
  indices = np.array(list(vectorizer.vocabulary_.values()))
  inverse_vocabulary = terms[np.argsort(indices)]
  tokenizer = vectorizer.build_tokenizer()
  print 'parsing train, test...',
  parsed_train = GetParsedDocuments(train_data, tokenizer)
  parsed_test = GetParsedDocuments(test_data, tokenizer)
  print 'done'
  print 'generating (or loading) json...',
  json_map = {}
  if args.loadjson:
    json_map = json.load(open(args.loadjson))
  else:  
    json_map = GenerateJSON(class_names, train_data, train_vectors, train_labels, test_data, test_vectors, test_labels, classifier, vectorizer)
  print 'done'
  if args.json:
    json.dump(json_map, open(args.json, 'w'))
  else:
    @route('/get_json', method=['OPTIONS', 'POST', 'GET'])
    @enable_cors
    def json_fun():
      global json_map
      return json_map
    @route('/predict', method=['OPTIONS', 'POST', 'GET'])
    @enable_cors
    def predict_fun():
        global train_vectors, train_labels, test_vectors, test_labels, classifier, tokenizer, parsed_train, parsed_test, json_map, class_names, inverse_vocabulary
        #print request.json
        ret = {}
        ex = ''
        if request.json['features']:
          ex = ' '.join(request.json['features'])
        sentence_explanation = request.json['sentence_explanation']
        v = vectorizer.transform([ex])
        #print 'Example:', ex
        #print 'Pred:'
        #print classifier.predict_proba(v)[0]
        ret['predict_proba'] = ListifyVector(classifier.predict_proba(v)[0])
        print ret['predict_proba']
        ret['prediction'] = classifier.predict(v)[0]
        #ret['feature_weights'] = WordImportance(classifier, v, inverse_vocabulary)
        if sentence_explanation:
          ret['feature_weights'] = WordImportanceSentenceGreedy(classifier, ex, vectorizer, inverse_vocabulary)
        else:
          ret['feature_weights'] = WordImportanceGreedy(classifier, ex, vectorizer, inverse_vocabulary)
        make_map = lambda x:{'feature':x[0], 'weight' : x[1]['weight'], 'class': x[1]['class']}
        ret['sorted_weights'] = map(make_map, sorted(ret['feature_weights'].iteritems(), key=lambda x:x[1]['weight'], reverse=True))
        return ret
    @route('/regex', method=['OPTIONS', 'POST', 'GET'])
    @enable_cors
    def regex_fun():
        global train_vectors, train_labels, test_vectors, test_labels, classifier, tokenizer, parsed_train, parsed_test, json_map, class_names, inverse_vocabulary
        ret = {}
        ex = ''
        print request.json
        if request.json['regex']:
          regex = re.sub(r'\\\\', r'\\', request.json['regex'])
        reg = re.compile(regex, re.DOTALL | re.MULTILINE)
        ret['train'] = {}
        for i, doc in enumerate(parsed_train):
          print i
          iterator = reg.finditer(doc)
          for m in iterator:
            if i not in ret['train']:
              ret['train'][i] = []
            ret['train'][i].append(m.span())
        ret['test'] = {}
        for i, doc in enumerate(parsed_test):
          print i
          iterator = reg.finditer(doc)
          for m in iterator:
            if i not in ret['test']:
              ret['test'][i] = []
            ret['test'][i].append(m.span())
        print 'Regex', regex
        return ret
    @route('/run_regex', method=['OPTIONS', 'POST', 'GET'])
    @enable_cors
    def regex_run():
        global train_vectors, train_labels, test_vectors, test_labels, classifier, tokenizer, parsed_train, parsed_test, json_map, class_names, inverse_vocabulary
        ex = ''
        print request.json
        regex_terms = set()
        if request.json['regex']:
          regexes = [(re.compile(re.sub(r'\\\\', r'\\', x.split('/')[1]), re.DOTALL | re.MULTILINE), x.split('/')[2]) for x in request.json['regex']]
        else:
          return json_map
        temp = []
        print 'Applying to train'
        for doc in parsed_train:
          d = doc
          for reg in regexes:
            instances = reg[0].findall(d)
            for instance in instances:
              map(lambda x: regex_terms.add(x), tokenizer(instance))
            d = re.sub(reg[0], reg[1], d)
          temp.append(d.strip(' '))
        parsed_train = temp
        temp = []
        print 'Applying to test'
        for doc in parsed_test:
          d = doc
          for reg in regexes:
            instances = reg[0].findall(d)
            for instance in instances:
              map(lambda x: regex_terms.add(x), tokenizer(instance))
            d = re.sub(reg[0], reg[1],d)
          temp.append(d.strip(' '))
        parsed_test = temp
        if len(regex_terms) > 100:
          regex_terms = set(vectorizer.vocabulary_.keys())
        # TODO: this could be much more efficient if I use a trie
        else:
          to_add = set()
          for w, i in vectorizer.vocabulary_.iteritems():
            for z in regex_terms:
              if w.startswith(z) or w.endswith(z):
                to_add.add(w)
          regex_terms = regex_terms.union(to_add)

        train_vectors = vectorizer.fit_transform(parsed_train)
        test_vectors = vectorizer.transform(parsed_test)
        classifier.fit(train_vectors, train_labels)
        terms = np.array(list(vectorizer.vocabulary_.keys()))
        indices = np.array(list(vectorizer.vocabulary_.values()))
        inverse_vocabulary = terms[np.argsort(indices)]
        # TODO: redoing some work here
        tokenizer = vectorizer.build_tokenizer()
        if request.json['regex']:
          for r in request.json['regex']:
            map(lambda x: regex_terms.add(x), tokenizer(r.split('/')[2]))
        print regex_terms
        print 'Updating Json'
        UpdateJSON(json_map, regex_terms, class_names, parsed_train, train_vectors, train_labels, parsed_test, test_vectors, test_labels, classifier, vectorizer)
        print 'Returning'
        return json_map
    @route('/')
    def root_fun():
        return template('template')
    @route('/<filename>')
    def server_static(filename):
        return static_file(filename, root='./static/')
    run(host='localhost', port=8870, debug=True)
  


if __name__ == "__main__":
    main()
