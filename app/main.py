import base64
import logging
import os
from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from typing import List

from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from facturx import generate_from_file
from fastapi import FastAPI, File, UploadFile, Query, Depends, APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

logger = logging.getLogger("uvicorn")
MAX_ATTACHMENTS = 3  # TODO make it a cmd line option

apm = make_apm_client()
app = FastAPI(openapi_url="/fusion/openapi.json", redoc_url="/fusion/redoc", docs_url="/fusion/docs")
app.add_middleware(ElasticAPM, client=apm)

prefix_router = APIRouter(prefix="/fusion")


@dataclass
class InputV2Model:
    pdfFile: UploadFile
    xmlFile: UploadFile
    attachments: List[UploadFile] = File(None)


@dataclass
class FileData:
    base64EncodedByteArrayData: str


@dataclass
class PJDtoItem:
    file: FileData
    name: str


@dataclass
class InputV1Model:
    pdf: FileData
    xml: FileData
    checkXml: bool = False
    licence: str = None
    folderId: str = None
    shortName: str = None
    functionnalLevel: str = None
    pJDto: List[PJDtoItem] = None


@dataclass
class PdfOutData:
    base64EncodedByteArrayData: str


@dataclass
class OutputV1ResultModel:
    returnCode: int
    output: str
    pdfOut: PdfOutData


@prefix_router.get("/api/health")
async def healthcheck():
    logger.info("Coucou")
    return "Healthy"


@prefix_router.post("/v1/GenerateFacturX")
async def generate_facture_x_v1(model: InputV1Model):
    decoded_pdf = base64.b64decode(model.pdf.base64EncodedByteArrayData)
    decoded_xml = base64.b64decode(model.xml.base64EncodedByteArrayData)
    decoded_pjs = {}

    if model.pJDto:
        if len(model.pJDto) > 0:
            for attachment in model.pJDto:
                decoded_pjs[attachment.name] = {
                    'filedata': base64.b64decode(attachment.file)
                }

    with NamedTemporaryFile(prefix='fx-api-inpdf-', suffix='.pdf') as pdf_file:
        pdf_file.write(decoded_pdf)
        pdf_file.seek(0)
        with NamedTemporaryFile(
                prefix='fx-api-outpdf-', suffix='.pdf') as output_pdf_file:
            logger.info('pdf_file.filename=%s', pdf_file.name)
            logger.info('output_pdf_file.name=%s', output_pdf_file.name)
            logger.info('attachments keys=%s', decoded_pjs.keys())
            logger.info('xmlCheck=%s', str(model.checkXml))
            generate_from_file(
                pdf_file.file, decoded_xml, output_pdf_file=output_pdf_file.name,
                attachments=decoded_pjs, check_xsd=model.checkXml)
            output_pdf_file.seek(0)
            return OutputV1ResultModel(returnCode=0,
                                       output="factur-x generated",
                                       pdfOut=PdfOutData(
                                           base64EncodedByteArrayData=base64.b64encode(
                                               output_pdf_file.read()).decode("utf-8")))


@prefix_router.post("/v2/GenerateFacturX")
async def generate_facture_x_v2(
        files: InputV2Model = Depends(),
        xmlCheck: bool = Query(default=False, description="Flag to check XML")):
    def cleanup():
        os.remove(output_pdf_file.name)

    logger.info('pdfFile.filename=%s', files.pdfFile.filename)
    logger.info('xmlFile.filename=%s', files.xmlFile.filename)

    attachments = {}
    if files.attachments:
        if len(files.attachments) > 0:
            for incr, a in enumerate(files.attachments):
                logger.info('attachments[%d]=%s', incr, a.filename)
                await a.seek(0)
                attachments[a.filename] = {
                    'filedata': await a.read(),
                }
                await a.close()
    await files.xmlFile.seek(0)
    xml_byte = await files.xmlFile.read()
    await files.xmlFile.close()

    with NamedTemporaryFile(
            prefix='fx-api-outpdf-', suffix='.pdf', delete=False) as output_pdf_file:
        logger.info('pdfFile.filename=%s', files.pdfFile.filename)
        logger.info('output_pdf_file.name=%s', output_pdf_file.name)
        logger.info('attachments keys=%s', attachments.keys())
        logger.info('xmlCheck=%s', str(xmlCheck))
        generate_from_file(
            files.pdfFile.file, xml_byte, output_pdf_file=output_pdf_file.name,
            attachments=attachments, check_xsd=xmlCheck)
        output_pdf_file.seek(0)
        return FileResponse(
            output_pdf_file.name,
            filename="file.pdf",
            media_type="application/octet-stream",
            background=BackgroundTask(cleanup))


app.include_router(prefix_router)
