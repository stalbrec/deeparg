import argparse
import sys
import logging
import traceback
import requests
import os
from tqdm import tqdm
from deeparg.short_reads_pipeline.short_reads_pipeline import main as main_srp
import zipfile
import subprocess
import deeparg.predict.bin.deepARG as clf

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)


def predict(args):

    if args.model == 'SS':
        mdl = '_SS'
        pipeline = 'reads'
    else:
        mdl = '_LS'
        pipeline = 'genes'

    if args.type == "prot":
        args.aligner = "blastp"
    else:
        args.aligner = "blastx"   

    logger.info("DIAMOND {} alignment".format(args.aligner))
    cmd = " ".join(['diamond ', args.aligner,
                        '-q', args.input_file,
                        '-d', args.data_path+"/database/"+args.model_version+"/features",
                        '-k', str(args.arg_num_alignments_per_entry),
                        '--id', str(args.arg_alignment_identity),
                        '--sensitive',
                        '-e', str(args.arg_alignment_evalue),
                        '-a', args.output_file+'.align'
                        ])
    logger.info('Running: {}'.format(cmd))
    diamond_align_proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    diamond_align_proc.communicate()

    logger.info("Input:{} output:{} model: deepARG{}, Input type: {}".format(args.input_file, args.output_file, mdl, args.aligner)) 

    cmd = " ".join([
        'diamond view',
        '-a', args.output_file+'.align.daa',
        '-o', args.output_file+'.align.daa.tsv'
    ])
    logger.info("parsing output file {}".format(cmd))
    diamond_view_proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    diamond_view_proc.communicate()

    clf.process(args.output_file+'.align.daa.tsv', args.output_file +
                '.mapping', args.arg_alignment_identity, mdl, args.arg_alignment_evalue, args.min_prob, args.arg_alignment_overlap, pipeline, args.model_version, args)

def mkdir(path):
    try:
        os.makedirs(path)
    except:
        logger.info("Directory {} already exists or couldn't create new directory".format(path))

def download_file(url, save_dir, type):
    r = requests.get(url, stream = True)
    logger.info("Downloading: {}".format(url))

    with open(save_dir, "wb") as ofile:
        for chunk in tqdm(r.iter_content(chunk_size = 1024)):
            if chunk:
                ofile.write(chunk)

def download_data(args):
    logger.info("Checking downloaded data {} Directory".format(args.output_path)) 
    main_url = 'https://zenodo.org/records/8280582/files/deeparg.zip'
    
    logger.info('Downloading Data from {}'.format(main_url))
    mkdir('{}'.format(args.output_path))
    download_file( "{}".format(main_url), "{}/deeparg.gz".format(args.output_path), "wb")

    with zipfile.ZipFile("{}/deeparg.gz".format(args.output_path), 'r') as zip_ref:
        zip_ref.extractall(args.output_path)

    os.system('mv {path}/deeparg/* {path}'.format(path=args.output_path))

def short_reads_pipeline(args):
    main_srp(args)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser.add_argument('--custom-model', action='store_true',
                       help='load custom model architecture from metadata.')

    # use deeparg section
    reads = subparsers.add_parser("predict", help="Predict ARG from reads or genes")
    reads.add_argument('--model', required=True,
                       help='Select model to use (short sequences for reads | long sequences for genes) SS|LS [No default]')
    reads.add_argument('-i', '--input-file', required=False,
                       help='Input file (Fasta input file)')
    reads.add_argument('-o', '--output-file', required=True,
                       help='Output file where to store results')
    reads.add_argument('-d', '--data-path', required=False,
                       help="Path where data was downloaded [see deeparg download-data --help for details]")
    reads.add_argument('--type', default='nucl',
                       help='Molecular data type prot/nucl [Default: nucl]')
    reads.add_argument('--min-prob', default=0.8, type=float,
                       help='Minimum probability cutoff [Default: 0.8]')
    reads.add_argument('--arg-alignment-identity', default=50, type=float,
                       help='Identity cutoff for sequence alignment in percent [Default: 50]')
    reads.add_argument('--arg-alignment-evalue', default=1e-10, type=float,
                       help='Evalue cutoff [Default: 1e-10]')
    reads.add_argument('--arg-alignment-overlap', default=0.8, type=float,
                       help='Alignment overlap cutoff between read and genes [Default: 0.8]')
    reads.add_argument('--arg-num-alignments-per-entry', default=1000, type=int,
                       help='Diamond, minimum number of alignments per entry [Default: 1000]')
    reads.add_argument('--model-version', default='v2',
                       help='Model deepARG version  [Default: v2]')
    reads.set_defaults(func=predict)

    # Download section
    download = subparsers.add_parser(
        "download_data", help="Download deeparg data")
    download.add_argument('-o', '--output_path', required=False,
                          help='output directory where to download data [Default: deepARG instalation directory]')
    download.set_defaults(func=download_data)

    # Short reads pipeline section
    short_reads_pipeline_parser = subparsers.add_parser("short_reads_pipeline", help="Predict ARG from reads")
    short_reads_pipeline_parser.add_argument("--forward_pe_file", type=str, required=True,
                        help="forward mate from paired end library",)
    short_reads_pipeline_parser.add_argument("--reverse_pe_file", type=str, required=True,
                        help="reverse mate from paired end library",)
    short_reads_pipeline_parser.add_argument("--output_file", type=str, required=True,
                        help="save results to this file prefix",)
    short_reads_pipeline_parser.add_argument('-d', '--deeparg_data_path', required=False,
                       help="Path where data was downloaded [see deeparg download-data --help for details]")
    short_reads_pipeline_parser.add_argument('--deeparg_model_version', default='v2',
                       help='Model deepARG version  [Default: v2]')
    short_reads_pipeline_parser.add_argument("--deeparg_identity", type=float, default=80,
                        help="minimum identity for ARG alignments [default 80]",)
    short_reads_pipeline_parser.add_argument("--deeparg_probability", type=float, default=0.8,
                        help="minimum probability for considering a reads as ARG-like [default 0.8]",)
    short_reads_pipeline_parser.add_argument("--deeparg_evalue", type=float, default=1e-10,
                        help="minimum e-value for ARG alignments [default 1e-10]",)
    short_reads_pipeline_parser.add_argument("--gene_coverage", type=float, default=1,
                        help="minimum coverage required for considering a full gene in percentage. This parameter looks at the full gene and all hits that align to the gene. If the overlap of all hits is below the threshold the gene is discarded. Use with caution [default 1]",)
    short_reads_pipeline_parser.add_argument("--bowtie_16s_identity", type=float, default=0.8,
                        help="minimum identity a read as a 16s rRNA gene [default 0.8]",)

    # short_reads_pipeline_parser.add_argument("--path_to_executables", type=str, default="/deeparg/short_reads_pipeline/bin/",
    #                     help="path to ./bin/ under short_reads_pipeline",)

    short_reads_pipeline_parser.set_defaults(func=short_reads_pipeline)

    # Get all arguments
    args = parser.parse_args()

    parser.parse_args()
    args.func(args)

    pass


if __name__ == '__main__':
    main()
