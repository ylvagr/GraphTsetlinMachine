from GraphTsetlinMachine.graphs import Graphs
import numpy as np
from scipy.sparse import csr_matrix
from GraphTsetlinMachine.tm import MultiClassGraphTsetlinMachine
from time import time
import argparse
from skimage.util import view_as_windows
from numba import jit
from keras.datasets import cifar10
import cv2

def horizontal_flip(image):
    return cv2.flip(image.astype(np.uint8), 1)

(X_train, Y_train), (X_test, Y_test) = cifar10.load_data()

X_train = X_train
Y_train = Y_train

X_test = X_test
Y_test = Y_test

Y_train = Y_train.reshape(Y_train.shape[0])
Y_test = Y_test.reshape(Y_test.shape[0])

for i in range(X_train.shape[0]):
        for j in range(X_train.shape[3]):
                X_train[i,:,:,j] = cv2.adaptiveThreshold(X_train[i,:,:,j], 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2) #cv2.adaptiveThreshold(X_train[i,:,:,j], 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 5, 5)

for i in range(X_test.shape[0]):
        for j in range(X_test.shape[3]):
                X_test[i,:,:,j] = cv2.adaptiveThreshold(X_test[i,:,:,j], 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)#cv2.adaptiveThreshold(X_test[i,:,:,j], 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 5, 5)

X_train = X_train.astype(np.uint32)
X_test = X_test.astype(np.uint32)
Y_train = Y_train.astype(np.uint32)
Y_test = Y_test.astype(np.uint32)

def default_args(**kwargs):
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", default=250, type=int)
    parser.add_argument("--number-of-clauses", default=40000, type=int)
    parser.add_argument("--T", default=7500, type=int)
    parser.add_argument("--s", default=20.0, type=float)
    parser.add_argument("--number-of-state-bits", default=8, type=int)
    parser.add_argument("--depth", default=1, type=int)
    parser.add_argument("--hypervector-size", default=128, type=int)
    parser.add_argument("--hypervector-bits", default=2, type=int)
    parser.add_argument("--message-size", default=256, type=int)
    parser.add_argument("--message-bits", default=2, type=int)
    parser.add_argument("--patch_size", default=8, type=int)
    parser.add_argument('--double-hashing', dest='double_hashing', default=False, action='store_true')
    parser.add_argument('--one-hot-encoding', dest='one_hot_encoding', default=False, action='store_true')
    parser.add_argument("--max-included-literals", default=32, type=int)

    args = parser.parse_args()
    for key, value in kwargs.items():
        if key in args.__dict__:
            setattr(args, key, value)
    return args

args = default_args()

dim = 32 - args.patch_size + 1

number_of_nodes = (dim * dim) * 2
print(number_of_nodes)

symbols = []

# Column and row symbols
for i in range(dim):
    symbols.append("C:%d" % (i))
    symbols.append("R:%d" % (i))

# Patch pixel symbols
for i in range(args.patch_size*args.patch_size*3):
    symbols.append(i)
    symbols.append("F:%d" % (i))

print(symbols)

graphs_train = Graphs(
    X_train.shape[0],
    symbols=symbols,
    hypervector_size=args.hypervector_size,
    hypervector_bits=args.hypervector_bits,
    double_hashing = args.double_hashing,
    one_hot_encoding = args.one_hot_encoding
)

for graph_id in range(X_train.shape[0]):
    graphs_train.set_number_of_graph_nodes(graph_id, number_of_nodes)

graphs_train.prepare_node_configuration()

for graph_id in range(X_train.shape[0]):
    for node_id in range(graphs_train.number_of_graph_nodes[graph_id]):
        graphs_train.add_graph_node(graph_id, node_id, 0)

graphs_train.prepare_edge_configuration()

for graph_id in range(X_train.shape[0]):
    if graph_id % 1000 == 0:
        print(graph_id, X_train.shape[0])
     
    windows = view_as_windows(X_train[graph_id,:,:,:], (args.patch_size, args.patch_size, 3))
    for q in range(windows.shape[0]):
            for r in range(windows.shape[1]):
                node_id = (q*dim + r) * 2

                patch = windows[q,r,0]
                flattened_patch = patch.reshape(-1).astype(np.uint32)
                # Original node
                for k in flattened_patch.nonzero()[0]:
                    graphs_train.add_graph_node_property(graph_id, node_id, k)
                for s in range(q + 1):
                    graphs_train.add_graph_node_property(graph_id, node_id, "C:%d" % s)
                for s in range(r + 1):
                    graphs_train.add_graph_node_property(graph_id, node_id, "R:%d" % s)

                # Flipped node
                flipped_patch = horizontal_flip(patch).reshape(-1).astype(np.uint32)
                node_id_flipped = node_id + 1
                for k in flipped_patch.nonzero()[0]:
                    graphs_train.add_graph_node_property(graph_id, node_id_flipped, "F:%d" % k)
                for s in range(q + 1):
                    graphs_train.add_graph_node_property(graph_id, node_id_flipped, "C:%d" % s)
                for s in range(r + 1):
                    graphs_train.add_graph_node_property(graph_id, node_id_flipped, "R:%d" % s)


graphs_train.encode()

print("Training data produced")

graphs_test = Graphs(X_test.shape[0], init_with=graphs_train)
for graph_id in range(X_test.shape[0]):
    graphs_test.set_number_of_graph_nodes(graph_id, number_of_nodes)

graphs_test.prepare_node_configuration()

for graph_id in range(X_test.shape[0]):
    for node_id in range(graphs_test.number_of_graph_nodes[graph_id]):
        graphs_test.add_graph_node(graph_id, node_id, 0)

graphs_test.prepare_edge_configuration()

for graph_id in range(X_test.shape[0]):
    if graph_id % 1000 == 0:
        print(graph_id, X_test.shape[0])
     
    windows = view_as_windows(X_test[graph_id,:,:], (args.patch_size, args.patch_size, 3))
    for q in range(windows.shape[0]):
            for r in range(windows.shape[1]):
                node_id = (q*dim + r) * 2

                patch = windows[q,r,0]
                flattened_patch = patch.reshape(-1).astype(np.uint32)
                for k in flattened_patch.nonzero()[0]:
                    graphs_test.add_graph_node_property(graph_id, node_id, k)

                for s in range(q+1):
                    graphs_test.add_graph_node_property(graph_id, node_id, "C:%d" % (s))

                for s in range(r+1):
                    graphs_test.add_graph_node_property(graph_id, node_id, "R:%d" % (s))

                flipped_patch = horizontal_flip(patch).reshape(-1).astype(np.uint32)
                node_id_flipped = node_id + 1
                for k in flipped_patch.nonzero()[0]:
                    graphs_test.add_graph_node_property(graph_id, node_id_flipped, "F:%d" % k)
                for s in range(q + 1):
                    graphs_test.add_graph_node_property(graph_id, node_id_flipped, "C:%d" % s)
                for s in range(r + 1):
                    graphs_test.add_graph_node_property(graph_id, node_id_flipped, "R:%d" % s)

graphs_test.encode()

print("Testing data produced")

tm = MultiClassGraphTsetlinMachine(
    args.number_of_clauses,
    args.T,
    args.s,number_of_state_bits = args.number_of_state_bits,
    depth=args.depth,
    message_size=args.message_size,
    message_bits=args.message_bits,
    max_included_literals=args.max_included_literals,
    double_hashing = args.double_hashing,
    one_hot_encoding = args.one_hot_encoding
)

for i in range(args.epochs):
    start_training = time()
    tm.fit(graphs_train, Y_train, epochs=1, incremental=True)
    stop_training = time()

    start_testing = time()
    result_test = 100*(tm.predict(graphs_test) == Y_test).mean()
    stop_testing = time()

    result_train = 100*(tm.predict(graphs_train) == Y_train).mean()

    print("%d %.2f %.2f %.2f %.2f" % (i, result_train, result_test, stop_training-start_training, stop_testing-start_testing))

weights = tm.get_state()[1].reshape(2, -1)
for i in range(tm.number_of_clauses):
        print("Clause #%d W:(%d %d)" % (i, weights[0,i], weights[1,i]), end=' ')
        l = []
        for k in range(args.hypervector_size * 2):
            if tm.ta_action(0, i, k):
                if k < args.hypervector_size:
                    l.append("x%d" % (k))
                else:
                    l.append("NOT x%d" % (k - args.hypervector_size))
        print(" AND ".join(l))


start_training = time()
tm.fit(graphs_train, Y_train, epochs=1, incremental=True)
stop_training = time()

start_testing = time()
result_test = 100*(tm.predict(graphs_test) == Y_test).mean()
stop_testing = time()

result_train = 100*(tm.predict(graphs_train) == Y_train).mean()

print("%.2f %.2f %.2f %.2f" % (result_train, result_test, stop_training-start_training, stop_testing-start_testing))

print(graphs_train.hypervectors)