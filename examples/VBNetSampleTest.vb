Imports NUnit.Framework
Imports System.Threading
Imports System.IO

Namespace TestProject
    <TestFixture>
    Public Class SampleTests
        <SetUp>
        Public Sub Setup()
            ' Setup code
        End Sub

        <Test>
        Public Sub TestAddition()
            Dim result As Integer = 2 + 2
            Assert.AreEqual(4, result)
        End Sub

        <Test>
        Public Sub TestWithSleep()
            ' BAD: Time-based wait
            Thread.Sleep(1000)
            Assert.IsTrue(True)
        End Sub

        <Test>
        Public Sub TestTooManyAssertions()
            ' BAD: Too many assertions
            Assert.AreEqual(1, 1)
            Assert.AreEqual(2, 2)
            Assert.AreEqual(3, 3)
            Assert.AreEqual(4, 4)
            Assert.AreEqual(5, 5)
        End Sub

        <Test>
        Public Sub TestNoAssertions()
            ' BAD: No assertions
            Dim x As Integer = 2 + 2
        End Sub

        <Test>
        Public Sub TestWithLogic()
            ' BAD: Conditional logic
            Dim value As Integer = 10
            If value > 5 Then
                Assert.IsTrue(value > 5)
            End If
        End Sub

        <Test>
        Public Sub TestFileIO()
            ' BAD: File I/O without fixture
            Dim content As String = File.ReadAllText("test.txt")
            Assert.IsNotNull(content)
        End Sub

        <Test>
        Public Async Function TestAsyncOperation() As Task
            ' Async test example
            Await Task.Delay(100)
            Assert.IsTrue(True)
        End Function
    End Class
End Namespace
