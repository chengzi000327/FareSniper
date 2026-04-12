import { NextResponse } from 'next/server'

const questions = ['五一去三亚，预算600', '北京上海随时', '下周末成都', '暑假带娃出行']

export function GET() {
  return NextResponse.json(questions)
}
