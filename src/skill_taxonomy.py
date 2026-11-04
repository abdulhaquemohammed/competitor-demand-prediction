"""
Shared skill taxonomy for all four companies (Task 4).

One dictionary: category -> {skill name: regex}. Every pattern is matched
case-insensitively against cleaned_description, except parts wrapped in
(?-i:...), which must match the exact case. That's used for short or ambiguous
words: "Go" the language vs "go-to-market", "R" the language vs the letter.

Seeded from the most common tech terms in the actual postings (see
notebooks/04_skills.ipynb), then grouped into the categories the brief gives
as examples (Cloud, ML, DevOps...). An empty pattern "" means "match the skill
name itself as a whole word".
"""

TAXONOMY = {
    "Programming Languages": {
        "Python": "",
        "Java": r"\bjava\b(?!\s*script)",
        "JavaScript": "",
        "TypeScript": "",
        "C++": r"(?<![\w+])c\+\+",
        "C": r"(?-i:(?<![\w+#/.-])C(?=\s*(?:/|,|and|or)\s*(?:C\+\+|Python|Java|Rust|Go)\b))|(?-i:\bC/C\+\+)",
        "C#": r"(?<![\w])c#",
        "Go": r"\bgolang\b|(?-i:\bGo\b(?!-)(?=\s*(?:,|/|\)|and\b|or\b)))|(?-i:(?<=[,/(] )Go\b(?!-))",
        "Rust": r"(?-i:\bRust\b)",
        "Scala": "",
        "Kotlin": "",
        "Swift": r"(?-i:\bSwift\b)",
        "R": r"(?-i:(?<![\w&/-])R(?=\s*(?:,|/|\)|and\b|or\b)\s*(?:Python|SQL|Julia|Scala|MATLAB|SAS)?))(?-i:(?![\w&]))",
        "SQL": r"\bsql\b",
        "MATLAB": "",
        "Bash / Shell": r"\bbash\b|\bshell scripting\b|\bshell scripts?\b",
        "Perl": "",
        "Tcl": r"\btcl\b",
        "Ruby": r"\bruby\b(?! on)|\bruby on rails\b",
        "Julia": r"(?-i:\bJulia\b)",
    },
    "ML Frameworks": {
        "PyTorch": "",
        "TensorFlow": "",
        "JAX": r"(?-i:\bJAX\b)",
        "scikit-learn": r"\bscikit-learn\b|\bsklearn\b",
        "Keras": "",
        "XGBoost": "",
        "Hugging Face": r"\bhugging ?face\b",
        "Ray": r"(?-i:\bRay\b)(?!\s*trac)",
        "MLflow": "",
        "pandas": r"(?-i:\bpandas\b)|\bPandas\b",
        "NumPy": "",
    },
    "ML & AI Concepts": {
        "Machine learning": r"\bmachine learning\b",
        "Deep learning": r"\bdeep learning\b",
        "LLMs": r"\bllms?\b|\blarge language models?\b",
        "Generative AI": r"\bgenerative ai\b|\bgenai\b|\bgen ai\b",
        "NLP": r"\bnlp\b|\bnatural language processing\b",
        "Computer vision": r"\bcomputer vision\b",
        "Reinforcement learning": r"\breinforcement learning\b|(?-i:\bRL\b)",
        "RLHF": r"\brlhf\b",
        "RAG": r"(?-i:\bRAG\b)|\bretrieval[- ]augmented\b",
        "Fine-tuning": r"\bfine[- ]?tun(e|ed|ing)\b",
        # ML transformers only, not electrical ones (NVIDIA power roles)
        "Transformers": r"\btransformer[- ](?:based|models?|architectures?)\b|\b(?:hugging face|vision) transformers?\b|"
                        r"\b(?:llms?|attention|diffusion|language model(?:ing|s)?)(?:,| and| or) transformers\b|"
                        r"\btransformers(?:,| and| or) (?:llms?|diffusion|attention|cnns?|rnns?)\b",
        "AI agents": r"\bai agents?\b|\bagentic\b|\bmulti-agent\b",
        "Evals": r"\bevals\b|\bmodel evaluations?\b",
        "Inference": r"\binference\b",
        "Distributed training": r"\bdistributed training\b|\blarge-scale training\b|\bpre-?training\b",
        "MLOps": r"\bmlops\b",
        "Recommender systems": r"\brecommend(er|ation) systems?\b",
        "Statistics": r"\bstatistic(s|al)\b",
        "Interpretability": r"\binterpretability\b",
        "AI safety / alignment": r"\bai safety\b|\b(ai|model|value) alignment\b|\balignment (research|team|science)\b|\bsafety research\b",
    },
    "LLM & Inference Tools": {
        "LangChain": "",
        "MCP": r"(?-i:\bMCP\b)|\bmodel context protocol\b",
        "vLLM": "",
        "SGLang": "",
        "TensorRT": r"\btensorrt(-llm)?\b",
        "Triton": r"(?-i:\bTriton\b)",
        "NeMo": r"(?-i:\bNeMo\b)",
        "NIM": r"(?-i:\bNIMs?\b)",
        "Vector databases": r"\bvector (databases?|db|stores?|search)\b|\bpinecone\b|\bweaviate\b|\bfaiss\b",
    },
    "Data Engineering & Analytics": {
        "Spark": r"\bspark(?:tm)?\b|\bpyspark\b",
        "Databricks": "",
        "Kafka": "",
        "Airflow": "",
        "dbt": r"(?-i:\bdbt\b)",
        "Snowflake": "",
        "BigQuery": "",
        "Hadoop": "",
        "Delta Lake": r"\bdelta lake\b",
        "ETL / ELT": r"\betl\b|\belt\b|\bdata pipelines?\b",
        "Data warehousing": r"\bdata ?warehous(e|es|ing)\b|\blakehouse\b",
        "Tableau": "",
        "Looker": "",
        "Power BI": r"\bpower ?bi\b",
        "Excel": r"(?-i:\bExcel\b)(?!\s+(?:at|in|as|when|with|across)\b)",  # not the verb "excel at"
    },
    "Databases": {
        "PostgreSQL": r"\bpostgres(ql)?\b",
        "MySQL": "",
        "MongoDB": "",
        "Redis": "",
        "Cassandra": "",
        "Elasticsearch": r"\belastic ?search\b",
        "DynamoDB": "",
        "OLTP": "",
    },
    "Cloud": {
        "AWS": r"\baws\b|\bamazon web services\b",
        "GCP": r"\bgcp\b|\bgoogle cloud\b",
        "Azure": "",
    },
    "DevOps & Infrastructure": {
        "Kubernetes": r"\bkubernetes\b|\bk8s\b",
        "Docker": "",
        "Terraform": "",
        "CI/CD": r"\bci/cd\b|\bcontinuous (integration|delivery|deployment)\b",
        "Linux": "",
        "Git": r"\bgit\b(?!hub|lab)",
        "GitHub": "",
        "Prometheus": "",
        "Grafana": "",
        "Observability": r"\bobservability\b",
        "SRE": r"(?-i:\bSREs?\b)|\bsite reliability\b",
        "Slurm": "",
        "Ansible": "",
        "Microservices": r"\bmicro-?services\b",
        "Distributed systems": r"\bdistributed systems?\b",
    },
    "GPU & HPC": {
        "CUDA": "",
        "GPU": r"\bgpus?\b",
        "HPC": r"\bhpc\b|\bhigh[- ]performance computing\b",
        "NCCL": "",
        "MPI": r"(?-i:\bMPI\b)",
        "OpenCL": "",
        "OpenMP": "",
        "RDMA": "",
        "InfiniBand": "",
        "NVLink": "",
        "cuDNN": "",
        "DGX": r"(?-i:\bDGX\b)",
        "Compilers": r"\bcompilers?\b|\bllvm\b|\bmlir\b",
        "Kernel optimisation": r"\bkernel (optimi[sz]ation|development)\b|\bgpu kernels?\b",
    },
    "Hardware & Semiconductor": {
        "ASIC": r"\basics?\b",
        "RTL": r"(?-i:\bRTL\b)",
        "Verilog / SystemVerilog": r"\b(system)?verilog\b",
        "VLSI": "",
        "FPGA": r"\bfpgas?\b",
        "PCIe": r"\bpci-?e\b|\bpci express\b",
        "DFT": r"(?-i:\bDFT\b)",
        "UVM": r"(?-i:\bUVM\b)",
        "EDA tools": r"(?-i:\bEDA\b)",
        "SoC": r"(?-i:\bSoCs?\b)|\bsystem[- ]on[- ]chip\b",
        "Static timing analysis": r"(?-i:\bSTA\b)|\bstatic timing\b",
        "PCB design": r"(?-i:\bPCBA?\b)",
        "Firmware": r"\bfirmware\b",
        "Embedded systems": r"\bembedded (?:systems?|software|firmware|linux|c\b|c\+\+|development|devices?|platforms?|processors?|engineer)",  # not "embedded in the team"
        "Physical design": r"\bphysical design\b",
        "Signal integrity": r"\bsignal integrity\b|\bserdes\b",
    },
    "Networking": {
        "TCP/IP": r"\btcp(/ip)?\b",
        "Ethernet": "",
        "RoCE": r"(?-i:\bRoCE\b)",
        "BGP": r"(?-i:\bBGP\b)",
        "OSPF": "",
        "VXLAN / EVPN": r"\bvxlan\b|\bevpn\b",
        "DNS": r"(?-i:\bDNS\b)",
        "Network protocols": r"\bnetwork(ing)? protocols?\b",
    },
    "Security": {
        "Security engineering": r"\bsecurity engineering\b|\bappsec\b|\bapplication security\b",
        "IAM": r"(?-i:\bIAM\b)|\bidentity and access\b",
        "OAuth": "",
        "Cryptography": r"\bcryptograph(y|ic)\b",
        "Threat modelling": r"\bthreat model(l)?ing\b",
        "Compliance (SOC 2, FedRAMP, ISO)": r"\bsoc ?2\b|\bfedramp\b|\biso ?27001\b",
        "Incident response": r"\bincident response\b",
    },
    "Web & APIs": {
        "React": r"(?-i:\bReact\b)",
        "Node.js": r"\bnode(\.js|js)\b",
        "REST APIs": r"\brest(ful)?\b(?= ?api)|\brestful\b",
        "GraphQL": "",
        "gRPC": "",
        "HTML / CSS": r"\bhtml\b|\bcss\b",
    },
    "Business & GTM": {
        "Salesforce": "",
        "MEDDPICC / MEDDIC": r"\bmeddp?icc?\b",
        "Go-to-market": r"(?-i:\bGTM\b)|\bgo[- ]to[- ]market\b",
        "Enterprise sales": r"\benterprise sales\b",
        "Stakeholder management": r"\bstakeholder management\b|\bmanag(e|ing) stakeholders\b",
        "Product management": r"\bproduct management\b",
    },
}

# A company's own product named in its own postings isn't a "skill" signal
SELF_MENTIONS = {"Databricks": {"Databricks"}}

# Concept and business categories describe topics, not tools, so they are
# left out of tech_stack_tags (the brief's example: AWS, Python, Kubernetes)
NOT_TECH_STACK = {"ML & AI Concepts", "Business & GTM"}


# ---------------------------------------------------------------- role categories

# First match wins, so specific titles come before broad ones ("Research Engineer"
# is research, "Solutions Architect" is solutions/field, not software engineering)
ROLE_CATEGORIES = [
    ("Research",              r"\bresearch|\bscientist\b"),
    ("Solutions & Field",     r"solutions? (architect|engineer)|forward deployed|\bfde\b|field (engineer|cto)|"
                              r"customer engineer|sales engineer|technical account|developer relations|"
                              r"applied ai (architect|engineer)|deployment strategist|\bsa\b"),
    ("Sales & Partnerships",  r"account (executive|manager|director)|\bsales\b|business development|partner|"
                              r"alliances?|customer success|\bgtm\b|revenue|\bae\b|country lead|digital natives|startups|"
                              r"\bgsi\b|outcomes manager|head of (?:asean|anz|emea|apac|latam|japan|korea|india|"
                              r"southern europe|northern europe|dach|uk|france|enterprise)"),
    ("Security",              r"\bsecurity\b|\bsecops\b|\btrust & safety\b|\bthreat\b"),
    ("Hardware Engineering",  r"\basic\b|\bhardware\b|\bverification\b|physical design|\bdft\b|\brtl\b|"
                              r"\bcircuit|\bthermal\b|\bmechanical\b|\bsilicon\b|\bsignal integrity\b|\bpcb\b|"
                              r"\bpackage design\b|\bvlsi\b|\banalog\b|\bpower\b.*engineer|\bboard\b"),
    ("ML / AI Engineering",   r"machine learning|\bml\b|\bai engineer|deep learning|\binference\b|\bllm\b|"
                              r"\bmodel|\btraining\b|\bperception\b|\bautonomous\b|\brobotics\b"),
    ("Data",                  r"\bdata (scien|analy|engineer)|\banalytics\b|\bdata\b(?! ?cent)"),  # not "data center"
    ("Software Engineering",  r"engineer|developer|\bswe\b|architect|\bprogrammer\b"),
    ("Product & Design",      r"product (manager|lead|director|designer|marketing)|\bdesign"),
    ("Program & Operations",  r"program manager|\btpm\b|operations|\bproject manager\b|\bsupply\b|"
                              r"\bprocurement\b|\blogistics\b|\bfacilities\b|\bwarehouse\b|\bsourcing\b|\breliability\b"),
    ("Marketing & Comms",     r"marketing|communications|\bcontent\b|\bbrand\b|\bevents?\b|\bcommunity\b|"
                              r"social media|\bgrowth\b|\beditor\b"),
    ("Corporate",             r"finance|\baccount(ant|ing)\b|legal|counsel|\bpeople\b|recruit|talent|\bhr\b|"
                              r"\btax\b|\bpolicy\b|\bcompliance\b|\baudit\b|\bpayroll\b|\bworkplace\b|"
                              r"executive assistant|\bstrategy\b|\bchief of staff\b|\bgovernment\b|compensation|"
                              r"\bconsolidation|\bsap\b"),
]
