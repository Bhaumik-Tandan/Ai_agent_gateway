import time
from typing import Dict, Optional
from pydantic import BaseModel


class ReadRequest(BaseModel):
    path: str


class ReadResponse(BaseModel):
    path: str
    content: str


class WriteRequest(BaseModel):
    path: str
    content: str


class WriteResponse(BaseModel):
    path: str
    status: str


class FilesAdapter:
    def __init__(self):
        self.files: Dict[str, str] = {
            '/hr-docs/employee-handbook.txt': 'Employee Handbook Version 2.0\n\nWelcome to the company...',
            '/hr-docs/benefits.txt': 'Benefits Information\n\nHealth Insurance: ...',
            '/legal/contract.docx': 'CONFIDENTIAL LEGAL CONTRACT\n\nThis agreement...'
        }
    
    def read(self, req: ReadRequest) -> ReadResponse:
        if not req.path:
            raise ValueError("path is required")
        
        if req.path not in self.files:
            raise ValueError(f"file '{req.path}' not found")
        
        time.sleep(0.005)
        
        return ReadResponse(
            path=req.path,
            content=self.files[req.path]
        )
    
    def write(self, req: WriteRequest) -> WriteResponse:
        if not req.path:
            raise ValueError("path is required")
        
        self.files[req.path] = req.content
        time.sleep(0.005)
        
        return WriteResponse(
            path=req.path,
            status="written"
        )

